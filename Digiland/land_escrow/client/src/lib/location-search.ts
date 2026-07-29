export type LandUseValue = 'Residential' | 'Commercial' | 'Agricultural';

export interface LocationSearchSuggestion {
  label: string;
  county: string;
  constituency: string;
  town?: string;
  region: string;
  description: string;
  landUse: LandUseValue;
  marketPosition: string;
  featured?: boolean;
}

export interface LocationSearchEntry extends LocationSearchSuggestion {
  normalizedLabel: string;
  normalizedLabelCompact: string;
  normalizedCounty: string;
  normalizedCountyCompact: string;
  normalizedConstituency: string;
  normalizedConstituencyCompact: string;
  normalizedTown: string;
  normalizedTownCompact: string;
  normalizedRegion: string;
  normalizedDescription: string;
  searchText: string;
  searchTextCompact: string;
  exactKeys: string[];
}

function collapseWhitespace(value: string) {
  return value.replace(/\s+/g, ' ').trim();
}

function compactLocationText(value: string) {
  return collapseWhitespace(value).replace(/\s+/g, '');
}

export function normalizeLocationQuery(value: string) {
  return collapseWhitespace(
    value
      .normalize('NFKD')
      .toLowerCase()
      .replace(/[_'’]/g, ' ')
      .replace(/[^a-z0-9]+/g, ' ')
  );
}

function marketPositionRank(position: string) {
  switch (position) {
    case 'Premium zone':
      return 4;
    case 'High-value zone':
      return 3.5;
    case 'Growth corridor':
      return 3.2;
    case 'Coastal demand':
      return 3.1;
    case 'Mid-market zone':
      return 2.6;
    case 'Emerging zone':
      return 2.2;
    case 'Market average':
      return 1.8;
    default:
      return 1.4;
  }
}

export function buildLocationSearchIndex(records: LocationSearchSuggestion[]): LocationSearchEntry[] {
  return records.map((record) => {
    const normalizedLabel = normalizeLocationQuery(record.label);
    const normalizedLabelCompact = compactLocationText(normalizedLabel);
    const normalizedCounty = normalizeLocationQuery(record.county);
    const normalizedCountyCompact = compactLocationText(normalizedCounty);
    const normalizedConstituency = normalizeLocationQuery(record.constituency);
    const normalizedConstituencyCompact = compactLocationText(normalizedConstituency);
    const normalizedTown = normalizeLocationQuery(record.town || record.label);
    const normalizedTownCompact = compactLocationText(normalizedTown);
    const normalizedRegion = normalizeLocationQuery(record.region);
    const normalizedDescription = normalizeLocationQuery(record.description);
    const searchText = collapseWhitespace(
      [
        normalizedLabel,
        normalizedLabelCompact,
        normalizedCounty,
        normalizedCountyCompact,
        normalizedConstituency,
        normalizedConstituencyCompact,
        normalizedTown,
        normalizedTownCompact,
        normalizedRegion,
        compactLocationText(normalizedRegion),
        normalizedDescription,
        compactLocationText(normalizedDescription),
        normalizeLocationQuery(record.marketPosition),
        normalizeLocationQuery(record.landUse),
      ]
        .filter(Boolean)
        .join(' ')
    );
    const searchTextCompact = compactLocationText(searchText);

    const exactKeys = Array.from(
      new Set([
        normalizedLabel,
        normalizedLabelCompact,
        normalizedCounty,
        normalizedCountyCompact,
        normalizedConstituency,
        normalizedConstituencyCompact,
        normalizedTown,
        normalizedTownCompact,
        searchText,
        searchTextCompact,
      ].filter(Boolean))
    );

    return {
      ...record,
      normalizedLabel,
      normalizedLabelCompact,
      normalizedCounty,
      normalizedCountyCompact,
      normalizedConstituency,
      normalizedConstituencyCompact,
      normalizedTown,
      normalizedTownCompact,
      normalizedRegion,
      normalizedDescription,
      searchText,
      searchTextCompact,
      exactKeys,
    };
  });
}

export function filterLocationSuggestions(
  entries: LocationSearchEntry[],
  query: string,
  limit = 8,
) {
  const normalizedQuery = normalizeLocationQuery(query);
  const normalizedQueryCompact = compactLocationText(normalizedQuery);
  const tokens = normalizedQuery ? normalizedQuery.split(' ').filter(Boolean) : [];

  const scored = entries
    .map((entry) => {
      if (!normalizedQuery) {
        return {
          entry,
          score:
            (entry.featured ? 100 : 0) +
            marketPositionRank(entry.marketPosition) * 10 +
            Math.max(0, 40 - entry.searchText.length / 15),
        };
      }

      if (!tokens.every((token) => entry.searchText.includes(token) || entry.searchTextCompact.includes(token))) {
        return null;
      }

      let score = 0;
      if (entry.exactKeys.includes(normalizedQuery) || entry.exactKeys.includes(normalizedQueryCompact)) score += 220;
      if (entry.normalizedLabel === normalizedQuery || entry.normalizedLabelCompact === normalizedQueryCompact) score += 180;
      if (entry.normalizedTown === normalizedQuery || entry.normalizedTownCompact === normalizedQueryCompact) score += 170;
      if (entry.normalizedConstituency === normalizedQuery || entry.normalizedConstituencyCompact === normalizedQueryCompact) score += 150;
      if (entry.normalizedCounty === normalizedQuery || entry.normalizedCountyCompact === normalizedQueryCompact) score += 140;
      if (entry.searchText.startsWith(normalizedQuery)) score += 120;
      if (entry.searchText.includes(normalizedQuery)) score += 90;
      if (entry.searchTextCompact.startsWith(normalizedQueryCompact)) score += 120;
      if (entry.searchTextCompact.includes(normalizedQueryCompact)) score += 90;
      score += tokens.length * 18;
      score += entry.featured ? 35 : 0;
      score += marketPositionRank(entry.marketPosition) * 8;
      score += Math.max(0, 55 - entry.searchText.length / 12);

      return { entry, score };
    })
    .filter((value): value is { entry: LocationSearchEntry; score: number } => value !== null)
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score;
      if (right.entry.featured !== left.entry.featured) return Number(right.entry.featured) - Number(left.entry.featured);
      return left.entry.label.localeCompare(right.entry.label);
    });

  return scored.slice(0, limit).map((item) => item.entry);
}

export function resolveLocationSuggestion(
  entries: LocationSearchEntry[],
  query: string,
) {
  const normalizedQuery = normalizeLocationQuery(query);
  const normalizedQueryCompact = compactLocationText(normalizedQuery);
  if (!normalizedQuery) {
    return null;
  }

  return (
    entries.find((entry) => entry.exactKeys.includes(normalizedQuery) || entry.exactKeys.includes(normalizedQueryCompact)) ||
    entries.find((entry) => entry.searchText.startsWith(normalizedQuery) || entry.searchTextCompact.startsWith(normalizedQueryCompact)) ||
    entries.find((entry) => entry.searchText.includes(normalizedQuery) || entry.searchTextCompact.includes(normalizedQueryCompact)) ||
    null
  );
}
