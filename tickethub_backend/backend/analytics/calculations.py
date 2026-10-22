def funnel_rows(counts, steps):
    if len(counts) != len(steps) or any(count < 0 for count in counts):
        raise ValueError('Invalid funnel')
    if any(later > earlier for earlier, later in zip(counts, counts[1:])):
        raise ValueError('A sequential funnel cannot grow')
    base = counts[0] if counts else 0
    result = []
    for index, (step, count) in enumerate(zip(steps, counts)):
        previous = counts[index - 1] if index else base
        result.append({'step': step, 'count': count,
                       'conversion_from_previous': round(count / previous, 4) if previous else None,
                       'overall_conversion': round(count / base, 4) if base else None})
    return result


def milestone_funnel(paths, steps):
    """All earlier facts must exist; payment may precede confirmation in real life."""
    counts = [0] * len(steps)
    for milestones in paths:
        for index, step in enumerate(steps):
            if step not in milestones:
                break
            counts[index] += 1
    return funnel_rows(counts, steps)


def chronological_funnel(paths, steps):
    """Each path is an ordered sequence; duplicates cannot inflate a conversion."""
    counts = [0] * len(steps)
    for sequence in paths:
        next_step = 0
        for step in sequence:
            if next_step < len(steps) and step == steps[next_step]:
                counts[next_step] += 1
                next_step += 1
    return funnel_rows(counts, steps)
