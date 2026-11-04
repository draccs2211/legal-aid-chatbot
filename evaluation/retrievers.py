"""Retrieval strategies that can be compared on the same labelled queries.

Each retriever has the signature  retriever(query, domain, k) -> [chunk, ...]
where every chunk is a dict with at least "id", "metadata" and "distance"
(lower distance = closer match).

Why `soft_route` exists
-----------------------
Baseline measurements showed the hard domain filter is all-or-nothing: queries
given the CORRECT domain hit 43/47, but the 6 queries given a WRONG domain hit
0/6, because the right chunk cannot be retrieved at all. A soft route never
removes candidates. It searches without a filter, adds the routed domain's
candidates, and gives chunks from the routed domain a small distance bonus
(`delta`). A wrong router can then displace the right chunk only when the right
chunk is already within `delta` of the wrong one.

`delta` is a tuned parameter. Pick it on the development set, then confirm on
queries nobody tuned against.
"""

_INF = float("inf")


def _distance(chunk):
    d = chunk.get("distance")
    return _INF if d is None else d


def make_soft_retriever(retrieve, domain_value, delta):
    """Build a soft-routing retriever.

    retrieve      function(query, domain, top_k) -> chunks   (domain may be None)
    domain_value  function(domain) -> value stored in the chunk metadata
    delta         distance bonus for chunks from the routed domain (>= 0)
    """
    def retriever(query, domain, k):
        routed = bool(domain) and domain != "general"
        pool = {}
        for chunk in retrieve(query, None, k):
            pool.setdefault(chunk["id"], chunk)
        wanted = None
        if routed:
            wanted = domain_value(domain)
            for chunk in retrieve(query, domain, k):
                pool.setdefault(chunk["id"], chunk)

        def adjusted(chunk):
            d = _distance(chunk)
            if wanted is not None and chunk.get("metadata", {}).get("domain") == wanted:
                return d - delta
            return d

        ranked = sorted(pool.values(), key=adjusted)[:k]
        return [dict(c, adjusted_distance=adjusted(c)) for c in ranked]

    return retriever
