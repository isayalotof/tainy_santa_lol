import random
from typing import List, Dict, Tuple


def secret_santa_draw(participants: List[int]) -> Dict[int, int]:
    """
    Generate Secret Santa assignments.

    Args:
        participants: List of user IDs

    Returns:
        Dictionary mapping giver_id -> receiver_id

    Raises:
        ValueError: If there are less than 2 participants
    """
    if len(participants) < 2:
        raise ValueError("Need at least 2 participants for Secret Santa")

    # Create a copy to shuffle
    givers = participants.copy()
    receivers = participants.copy()

    # Try to create valid assignment (no one gets themselves)
    max_attempts = 100
    for attempt in range(max_attempts):
        random.shuffle(receivers)

        # Check if anyone got themselves
        valid = True
        for i, giver in enumerate(givers):
            if giver == receivers[i]:
                valid = False
                break

        if valid:
            # Create the assignment dictionary
            assignments = {}
            for i, giver in enumerate(givers):
                assignments[giver] = receivers[i]
            return assignments

    # Fallback: use derangement algorithm for guaranteed solution
    return _derangement_draw(participants)


def _derangement_draw(participants: List[int]) -> Dict[int, int]:
    """
    Generate derangement (permutation where no element appears in its original position).
    This guarantees a valid Secret Santa assignment.
    """
    n = len(participants)
    givers = participants.copy()
    receivers = participants.copy()

    # Simple rotation by 1 guarantees no one gets themselves
    random.shuffle(givers)
    receivers = givers[1:] + [givers[0]]

    assignments = {}
    for i, giver in enumerate(givers):
        assignments[giver] = receivers[i]

    return assignments


def validate_draw(assignments: Dict[int, int]) -> bool:
    """
    Validate that Secret Santa draw is correct:
    - No one assigned to themselves
    - Everyone gives exactly once
    - Everyone receives exactly once
    """
    if not assignments:
        return False

    givers = set(assignments.keys())
    receivers = set(assignments.values())

    # Check everyone gives and receives
    if givers != receivers:
        return False

    # Check no one got themselves
    for giver, receiver in assignments.items():
        if giver == receiver:
            return False

    return True
