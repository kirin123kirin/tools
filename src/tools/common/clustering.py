from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def agglomerative_average_linkage(
    distance_matrix: NDArray[np.float64], distance_threshold: float
) -> NDArray[np.int_]:
    """Average-linkage agglomerative clustering via the Lance-Williams update.

    Equivalent to `sklearn.cluster.AgglomerativeClustering(metric="precomputed",
    linkage="average", distance_threshold=distance_threshold, n_clusters=None)`
    (verified against sklearn on random inputs during development).

    Clusters are merged, closest pair first, until the closest remaining pair
    exceeds `distance_threshold`. Merged-cluster distances are updated in O(1)
    per neighbor via Lance-Williams (`d(k, i∪j) = (|i|·d(k,i) + |j|·d(k,j)) / (|i|+|j|)`)
    rather than recomputed from scratch, keeping updates to O(n^2) overall
    (finding the closest pair each round is still a linear scan).

    Returns a 0-indexed label array, one entry per input row.
    """
    n = distance_matrix.shape[0]
    if n == 0:
        return np.array([], dtype=int)
    if n == 1:
        return np.array([0], dtype=int)

    sizes: dict[int, int] = {i: 1 for i in range(n)}
    members: dict[int, list[int]] = {i: [i] for i in range(n)}
    dist: dict[tuple[int, int], float] = {}
    for i in range(n):
        for j in range(i + 1, n):
            dist[(i, j)] = float(distance_matrix[i, j])

    def get_dist(a: int, b: int) -> float:
        return dist[(a, b)] if a < b else dist[(b, a)]

    def set_dist(a: int, b: int, value: float) -> None:
        if a < b:
            dist[(a, b)] = value
        else:
            dist[(b, a)] = value

    active = list(range(n))
    next_id = n

    while len(active) > 1:
        best_pair: tuple[int, int] | None = None
        best_distance: float | None = None
        for ai in range(len(active)):
            for bi in range(ai + 1, len(active)):
                a, b = active[ai], active[bi]
                d = get_dist(a, b)
                if best_distance is None or d < best_distance:
                    best_distance = d
                    best_pair = (a, b)

        assert best_pair is not None and best_distance is not None
        if best_distance > distance_threshold:
            break

        a, b = best_pair
        new_id = next_id
        next_id += 1
        size_a, size_b = sizes[a], sizes[b]
        new_size = size_a + size_b
        members[new_id] = members[a] + members[b]
        sizes[new_id] = new_size

        for k in active:
            if k in (a, b):
                continue
            new_d = (size_a * get_dist(k, a) + size_b * get_dist(k, b)) / new_size
            set_dist(k, new_id, new_d)

        active = [x for x in active if x not in (a, b)]
        active.append(new_id)

    labels = np.zeros(n, dtype=int)
    for label, cluster_id in enumerate(active):
        for member in members[cluster_id]:
            labels[member] = label
    return labels
