def _normalize_reward(reward: float) -> float:
    return min(max(float(reward), 0.0), 1.0)


def grade_task_0(state: dict, reward: float) -> float:
    return _normalize_reward(reward)


def grade_task_1(state: dict, reward: float) -> float:
    return _normalize_reward(reward)


def grade_task_2(state: dict, reward: float) -> float:
    return _normalize_reward(reward)


GRADERS = {
    "sre-pod-crashloop": grade_task_0,
    "sre-db-timeout": grade_task_1,
    "sre-high-latency": grade_task_1,
    "sre-node-pressure": grade_task_2,
    "sre-security-anomaly": grade_task_2,
    "sre-compound-chaos": grade_task_2,
}

TASK_GRADER_PAIRS = [
    ("sre-pod-crashloop", grade_task_0),
    ("sre-db-timeout", grade_task_1),
    ("sre-high-latency", grade_task_1),
    ("sre-node-pressure", grade_task_2),
    ("sre-security-anomaly", grade_task_2),
    ("sre-compound-chaos", grade_task_2),
]

__all__ = [
    "grade_task_0",
    "grade_task_1",
    "grade_task_2",
    "GRADERS",
    "TASK_GRADER_PAIRS",
]
