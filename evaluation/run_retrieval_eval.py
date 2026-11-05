"""Measure retrieval quality on evaluation/data/retrieval_labelled.json.

Run from the repo root (after scripts/load_chromadb.py):

    python evaluation/run_retrieval_eval.py --label baseline
    python evaluation/run_retrieval_eval.py --label soft --retrievers baseline,soft_0.10 --modes routed
    python evaluation/run_retrieval_eval.py --label deep --modes oracle,unfiltered --k-max 30

Retriever specs (comma-separated in --retrievers):
    baseline                         production Chroma index, default embedder
    soft_0.15                        baseline + soft routing with that delta
    st:<hf-model-id>                 in-memory index built with a sentence-transformers model
    st:<hf-model-id>+soft_0.15       the same, plus soft routing

Language experiment (same questions, three phrasings; labels are inherited):
    python evaluation/run_retrieval_eval.py --label lang_hi --quiet \
        --parallel evaluation/data/retrieval_parallel.json --variant hi --modes oracle,unfiltered

Three modes separate different failure causes:
  routed      domain chosen by the app's keyword router (what users get today)
  oracle      the labelled domain is used as the filter (embedding quality
              with perfect routing)
  unfiltered  no domain filter at all (embedding quality, no routing help)

Results are written to evaluation/results/<label>.json so later runs
(reranker, other embedding model, ...) can be compared against the baseline.

CAVEAT: the labels were drafted by one person (and an AI assistant) and still
need review by a second person and, for legal correctness, by a lawyer.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from evaluation import metrics as M  # noqa: E402
from evaluation.retrievers import make_soft_retriever  # noqa: E402

DATA = os.path.join(ROOT, "evaluation", "data", "retrieval_labelled.json")
RESULTS = os.path.join(ROOT, "evaluation", "results")


# ---------------------------------------------------------------------------
# Retrievers are built from a spec string (see the module docstring).
# A retriever is a function(query, domain, k) -> [{"id", "distance", ...}].
# ---------------------------------------------------------------------------
_INDEX_CACHE = {}


def parse_spec(spec):
    """'st:model+soft_0.15' -> ('st:model', 0.15); 'soft_0.10' -> ('baseline', 0.10)."""
    base, _, soft = spec.strip().partition("+")
    delta = None
    try:
        if soft:
            if not soft.startswith("soft_"):
                raise ValueError
            delta = float(soft[len("soft_"):])
        if base.startswith("soft_"):
            if delta is not None:
                raise ValueError
            delta, base = float(base[len("soft_"):]), "baseline"
    except ValueError:
        raise ValueError(f"Bad retriever spec: {spec!r}") from None
    if base != "baseline" and not (base.startswith("st:") and len(base) > 3):
        raise ValueError(f"Bad retriever spec: {spec!r} (use baseline, soft_<d>, st:<model>[+soft_<d>])")
    if delta is not None and delta < 0:
        raise ValueError(f"Bad retriever spec: {spec!r} (delta must be >= 0)")
    return base, delta


def build_retriever(spec, embedder_factory=None):
    """Return (retriever, info) for a spec. info describes the embedding model."""
    from rag_pipeline import chroma_domain_value, retrieve_chunks

    base, delta = parse_spec(spec)
    info = {}
    if base == "baseline":
        def retrieve(query, domain, k):
            return retrieve_chunks(query, domain=domain, top_k=k)
    else:
        model = base[3:]
        if model not in _INDEX_CACHE:
            from evaluation import embedders
            from config import DATA_DIR
            factory = embedder_factory or embedders.sentence_transformer_embedders
            embed_docs, embed_query, model_info = factory(model)
            collection = embedders.build_index(embedders.load_chunks(DATA_DIR), embed_docs)
            _INDEX_CACHE[model] = (
                embedders.make_index_retriever(collection, embed_query, chroma_domain_value), model_info)
        retrieve, info = _INDEX_CACHE[model]
    if delta is None:
        return retrieve, info
    return make_soft_retriever(retrieve, chroma_domain_value, delta), info


VARIANT_LANG = {"en": "en", "hi": "devanagari", "awa": "awadhi", "bns": "bundeli"}
DIALECT_VARIANTS = ("awa", "bns")


def apply_variant(dataset, translations, variant):
    """Keep only queries that have a parallel entry for this phrasing and, for
    anything but 'original', swap that phrasing in. Labels are inherited.

    variant: original | en | hi | awa (Awadhi) | bns (Bundeli). Entries with no
    (or an empty) text for a dialect are skipped, so a half-filled file works.
    """
    if variant != "original" and variant not in VARIANT_LANG:
        raise ValueError("variant must be original, en, hi, awa or bns")
    out = []
    for item in dataset:
        entry = translations.get(item["id"])
        if entry is None:
            continue
        new = dict(item)
        if variant != "original":
            text = (entry.get(variant) or "").strip()
            if not text:
                continue
            new["query"] = text
            new["lang"] = VARIANT_LANG[variant]
        out.append(new)
    return out


def unreviewed_count(translations, dataset, variant):
    """How many used dialect entries have no reviewer recorded (<variant>_by)."""
    if variant not in DIALECT_VARIANTS:
        return 0
    return sum(1 for item in dataset if not (translations.get(item["id"], {}).get(variant + "_by") or "").strip())


def safe_name(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")


def evaluate(dataset, retriever, mode, k_max, k_values, router=None):
    """Run one mode over the dataset. Returns per-query records."""
    records = []
    for item in dataset:
        if mode == "routed":
            domain = router(item["query"])
        elif mode == "oracle":
            domain = item["expected_domain"] if item["answerable"] else "general"
        else:
            domain = "general"
        chunks = retriever(item["query"], domain, k_max)
        ranking = [c["id"] for c in chunks]
        rec = {
            "id": item["id"], "query": item["query"], "lang": item["lang"],
            "qtype": item["qtype"], "answerable": item["answerable"],
            "expected_domain": item["expected_domain"], "used_domain": domain,
            "ranking": ranking,
            "distances": [c.get("distance") for c in chunks],
            "top1_distance": chunks[0].get("distance") if chunks else None,
        }
        if item["answerable"]:
            rec["scores"] = M.score_query(ranking, item["relevant"], k_values)
            rec["relevant"] = item["relevant"]
        records.append(rec)
    return records


def summarize(records, k_values):
    ans = [r for r in records if r["answerable"]]
    unans = [r for r in records if not r["answerable"]]
    out = {
        "n_answerable": len(ans),
        "n_unanswerable": len(unans),
        "overall": M.aggregate([r["scores"] for r in ans]),
        "by_lang": {g: M.aggregate([r["scores"] for r in rs]) | {"n": len(rs)}
                    for g, rs in M.group_by(ans, "lang").items()},
        "by_qtype": {g: M.aggregate([r["scores"] for r in rs]) | {"n": len(rs)}
                     for g, rs in M.group_by(ans, "qtype").items()},
        "top1_distance_answerable": M.distance_summary([r["top1_distance"] for r in ans]),
        "top1_distance_unanswerable": M.distance_summary([r["top1_distance"] for r in unans]),
        "threshold_table": M.threshold_table([r["top1_distance"] for r in ans],
                                             [r["top1_distance"] for r in unans]),
    }
    return out


def fmt(x):
    return "  n/a" if x is None else f"{x:5.3f}"


def print_report(mode, summary, records, k_values, k_app):
    print("\n" + "=" * 78)
    print(f"MODE: {mode}   (answerable={summary['n_answerable']}, unanswerable={summary['n_unanswerable']})")
    print("=" * 78)
    o = summary["overall"]
    print(f"{'K':>4} {'Hit@K':>7} {'Recall@K':>9} {'Prec@K':>7} {'nDCG@K':>7}")
    for k in k_values:
        mark = "  <- K used by the app" if k == k_app else ""
        print(f"{k:>4} {fmt(o[f'hit@{k}']):>7} {fmt(o[f'recall@{k}']):>9} "
              f"{fmt(o[f'precision@{k}']):>7} {fmt(o[f'ndcg@{k}']):>7}{mark}")
    print(f"MRR (first grade-2 chunk): {fmt(o['mrr'])}")

    for title, key in (("By language", "by_lang"), ("By query type", "by_qtype")):
        print(f"\n{title} (Hit@{k_app} / MRR):")
        for g, s in sorted(summary[key].items()):
            print(f"  {g:<14} n={s['n']:<3} Hit@{k_app}={fmt(s[f'hit@{k_app}'])}  MRR={fmt(s['mrr'])}")

    misses = [r for r in records if r["answerable"] and r["scores"][f"hit@{k_app}"] == 0.0]
    print(f"\nAnswerable queries with NO grade-2 chunk in top {k_app}: {len(misses)}")
    for r in misses[:15]:
        want = [c for c, g in r["relevant"].items() if g == 2]
        print(f"  {r['id']} [{r['lang']}] {r['query']}")
        print(f"      wanted: {want}")
        print(f"      got:    {r['ranking'][:k_app]}  (domain filter: {r['used_domain']})")

    a, u = summary["top1_distance_answerable"], summary["top1_distance_unanswerable"]
    if a and u:
        print("\nTop-1 distance (lower = closer):")
        print(f"  answerable   : min={a['min']:.3f} median={a['median']:.3f} max={a['max']:.3f}")
        print(f"  unanswerable : min={u['min']:.3f} median={u['median']:.3f} max={u['max']:.3f}")
        print("  Abstain-if-distance-above threshold (grounding gate candidates):")
        print(f"  {'threshold':>10} {'answerable kept':>16} {'unanswerable rejected':>22}")
        for row in summary["threshold_table"]:
            print(f"  {row['threshold']:>10.3f} {row['answered_kept']:>16.2f} {row['unanswerable_rejected']:>22.2f}")


def comparison_rows(summaries, k_app):
    """One row per (retriever, mode): the numbers worth comparing side by side."""
    rows = []
    for (name, mode), summ in summaries.items():
        o = summ["overall"]
        lang = summ["by_lang"]
        rows.append({
            "retriever": name, "mode": mode,
            f"hit@{k_app}": o[f"hit@{k_app}"], "hit@10": o.get("hit@10"),
            "mrr": o["mrr"], f"ndcg@{k_app}": o[f"ndcg@{k_app}"],
            "hit_en": lang.get("en", {}).get(f"hit@{k_app}"),
            "hit_hinglish": lang.get("hinglish", {}).get(f"hit@{k_app}"),
            "hit_devanagari": lang.get("devanagari", {}).get(f"hit@{k_app}"),
        })
    return rows


def print_comparison(rows, k_app):
    print("\n" + "=" * 132)
    print("COMPARISON (answerable queries)")
    print("=" * 132)
    print(f"{'retriever':<44}{'mode':<11}{'Hit@'+str(k_app):>7}{'Hit@10':>8}{'MRR':>7}{'nDCG@'+str(k_app):>8}"
          f"{'en':>7}{'hinglish':>10}{'devanagari':>12}")
    for r in rows:
        print(f"{r['retriever']:<44}{r['mode']:<11}{fmt(r[f'hit@{k_app}']):>7}{fmt(r['hit@10']):>8}{fmt(r['mrr']):>7}"
              f"{fmt(r[f'ndcg@{k_app}']):>8}{fmt(r['hit_en']):>7}{fmt(r['hit_hinglish']):>10}{fmt(r['hit_devanagari']):>12}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="baseline", help="name for the results file")
    ap.add_argument("--retrievers", default="baseline",
                    help="comma-separated specs: baseline, soft_<delta>, st:<model>[+soft_<delta>]")
    ap.add_argument("--modes", default="routed,oracle,unfiltered")
    ap.add_argument("--k-max", type=int, default=10,
                    help="retrieve this many per query (try 30 to size a reranker pool)")
    ap.add_argument("--parallel", help="path to a parallel-translations JSON (see retrieval_parallel.json)")
    ap.add_argument("--variant", default="original", choices=["original", "en", "hi", "awa", "bns"],
                    help="with --parallel: which phrasing of each question to use")
    ap.add_argument("--quiet", action="store_true", help="print only the comparison table")
    args = ap.parse_args()

    names = [n.strip() for n in args.retrievers.split(",") if n.strip()]
    for n in names:
        try:
            parse_spec(n)
        except ValueError as e:
            sys.exit(str(e))

    from config import TOP_K_RESULTS
    from rag_pipeline import get_collection, get_collection_stats
    from intent_detector import detect_domain

    stats = get_collection_stats()
    if stats["total_chunks"] == 0:
        sys.exit("ChromaDB is empty. Run: python scripts/load_chromadb.py first")

    with open(DATA, encoding="utf-8") as f:
        raw = f.read()
    dataset = json.loads(raw)
    if args.parallel:
        with open(args.parallel, encoding="utf-8") as f:
            translations = json.load(f)["translations"]
        dataset = apply_variant(dataset, translations, args.variant)
        if not dataset:
            sys.exit(f"No entries for variant '{args.variant}' yet. Fill evaluation/templates/"
                     "dialect_queries_template.csv and run evaluation/import_dialects.py first.")
        print(f"Parallel experiment: variant={args.variant}, {len(dataset)} queries")
        n_unrev = unreviewed_count(translations, dataset, args.variant)
        if n_unrev:
            print(f"WARNING: {n_unrev} of {len(dataset)} '{args.variant}' queries have no reviewer recorded. "
                  "Treat the numbers as provisional until a native speaker has reviewed them.")
    k_values = [k for k in (1, 3, 5, 10, 20, 30) if k <= args.k_max]

    routing = [(d, detect_domain(d["query"])) for d in dataset if d["answerable"]]
    routing_ok = sum(1 for d, got in routing if got == d["expected_domain"])
    print(f"Router accuracy on answerable queries: {routing_ok}/{len(routing)}")
    if not args.quiet:
        for d, got in routing:
            if got != d["expected_domain"]:
                print(f"  misrouted: expected={d['expected_domain']:<13} got={got:<13} | {d['query']}")

    emb = {}
    try:
        col = get_collection()
        ef = getattr(col, "_embedding_function", None)
        emb["embedding_function"] = type(ef).__name__ if ef is not None else None
        emb["distance_space"] = (getattr(col, "configuration", None) or {}).get("hnsw", {}).get("space")
    except Exception:
        pass

    summaries = {}
    for name in names:
        retriever, model_info = build_retriever(name)
        report = {
            "label": args.label, "retriever": name, "variant": args.variant if args.parallel else None,
            "date": datetime.datetime.now().isoformat(timespec="seconds"),
            "dataset_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
            "n_queries": len(dataset), "collection": stats, "k_app": TOP_K_RESULTS,
            "router_accuracy": [routing_ok, len(routing)], "modes": {},
            "embedding_model": model_info or None, **emb,
        }
        if model_info:
            print(f"[{name}] embedding model info: {model_info}")
        try:
            import chromadb
            report["chromadb_version"] = chromadb.__version__
        except Exception:
            pass

        for mode in [m.strip() for m in args.modes.split(",") if m.strip()]:
            records = evaluate(dataset, retriever, mode, args.k_max, k_values, router=detect_domain)
            summary = summarize(records, k_values)
            if not args.quiet:
                print(f"\n##### retriever={name} #####")
                print_report(mode, summary, records, k_values, TOP_K_RESULTS)
            report["modes"][mode] = {"summary": summary, "records": records}
            summaries[(name, mode)] = summary

        os.makedirs(RESULTS, exist_ok=True)
        fname = f"{args.label}.json" if len(names) == 1 else f"{args.label}_{safe_name(name)}.json"
        path = os.path.join(RESULTS, fname)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f"Saved {path}")

    if args.parallel:
        print(f"\n>>> variant={args.variant}  ({len(dataset)} queries)")
    print_comparison(comparison_rows(summaries, TOP_K_RESULTS), TOP_K_RESULTS)


if __name__ == "__main__":
    main()
