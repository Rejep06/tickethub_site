/** A checkbox accepts an exact document version, never a silently upgraded revision. */
export function acceptedDocuments(required: Record<string, number>, accepted: Record<string, number>): Record<string, number> {
    const result: Record<string, number> = {};
    for (const [slug, version] of Object.entries(required)) {
        if (accepted[slug] !== version)
            throw new Error('CONSENT_REQUIRED');
        result[slug] = version;
    }
    return result;
}
