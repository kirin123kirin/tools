import numpy as np
import pytest

from workpytools.common.clustering import agglomerative_average_linkage


def _normalize_labels(labels: list[int]) -> list[int]:
    mapping: dict[int, int] = {}
    result = []
    for label in labels:
        if label not in mapping:
            mapping[label] = len(mapping)
        result.append(mapping[label])
    return result


def _same_partition(a: list[int], b: list[int]) -> bool:
    n = len(a)
    for i in range(n):
        for j in range(n):
            if (a[i] == a[j]) != (b[i] == b[j]):
                return False
    return True


def test_single_point_returns_single_label() -> None:
    labels = agglomerative_average_linkage(np.zeros((1, 1)), distance_threshold=0.5)
    assert list(labels) == [0]


def test_empty_input_returns_empty() -> None:
    labels = agglomerative_average_linkage(np.zeros((0, 0)), distance_threshold=0.5)
    assert len(labels) == 0


def test_two_close_points_merge() -> None:
    dist = np.array([[0.0, 0.05], [0.05, 0.0]])
    labels = agglomerative_average_linkage(dist, distance_threshold=0.2)
    assert labels[0] == labels[1]


def test_two_far_points_stay_separate() -> None:
    dist = np.array([[0.0, 0.9], [0.9, 0.0]])
    labels = agglomerative_average_linkage(dist, distance_threshold=0.2)
    assert labels[0] != labels[1]


def test_threshold_boundary_merges_when_equal() -> None:
    dist = np.array([[0.0, 0.2], [0.2, 0.0]])
    labels = agglomerative_average_linkage(dist, distance_threshold=0.2)
    assert labels[0] == labels[1]


def test_threshold_boundary_stays_separate_when_just_over() -> None:
    dist = np.array([[0.0, 0.2000001], [0.2000001, 0.0]])
    labels = agglomerative_average_linkage(dist, distance_threshold=0.2)
    assert labels[0] != labels[1]


@pytest.mark.parametrize("seed", range(10))
def test_matches_sklearn_on_random_inputs(seed: int) -> None:
    sklearn_cluster = pytest.importorskip("sklearn.cluster")

    rng = np.random.default_rng(seed)
    n = rng.integers(3, 12)
    dim = 8
    vecs = rng.normal(size=(n, dim))
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    dist_matrix = 1 - (vecs @ vecs.T)
    np.fill_diagonal(dist_matrix, 0.0)
    threshold = float(rng.uniform(0.1, 0.6))

    mine = agglomerative_average_linkage(dist_matrix, threshold)
    sk = sklearn_cluster.AgglomerativeClustering(
        metric="precomputed",
        linkage="average",
        distance_threshold=threshold,
        n_clusters=None,
    ).fit(dist_matrix)

    assert _same_partition(
        _normalize_labels(list(mine)), _normalize_labels(list(sk.labels_))
    )
