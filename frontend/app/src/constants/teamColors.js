/**
 * NCAA team primary brand colors for the 2026 tournament field.
 * Used in championship probability pie charts and team-level visualizations.
 *
 * Colors sourced from official team brand guidelines.
 */

const TEAM_COLORS = {
  // East Region
  'Duke':               '#003087',
  'UConn':              '#000E2F',
  'Michigan State':     '#18453B',
  'Kansas':             '#0051BA',
  "St. John's":         '#BA0C2F',
  'Louisville':         '#AD0000',
  'UCLA':               '#2D68C4',
  'Ohio State':         '#BB0000',
  'TCU':                '#4D1979',
  'UCF':                '#BA9B37',
  'South Florida':      '#006747',
  'Northern Iowa':      '#4B116F',
  'Cal Baptist':        '#002855',
  'North Dakota State': '#0A5640',
  'Furman':             '#582C83',
  'Siena':              '#006747',

  // South Region
  'Florida':            '#0021A5',
  'Houston':            '#C8102E',
  'Illinois':           '#E84A27',
  'Nebraska':           '#E41C38',
  'Vanderbilt':         '#866D4B',
  'North Carolina':     '#7BAFD4',
  "Saint Mary's":       '#D50032',
  'Clemson':            '#F56600',
  'Iowa':               '#FFCD00',
  'Texas A&M':          '#500000',
  'VCU':                '#F8B800',
  'McNeese':            '#00529B',
  'Troy':               '#8B2332',
  'Penn':               '#011F5B',
  'Idaho':              '#B5A36A',
  'Prairie View A&M':   '#4F2D7F',
  'Lehigh':             '#6C3F18',

  // West Region
  'Arizona':            '#CC0033',
  'Purdue':             '#CEB888',
  'Gonzaga':            '#002967',
  'Arkansas':           '#9D2235',
  'Wisconsin':          '#C5050C',
  'BYU':                '#002E5D',
  'Miami':              '#F47321',
  'Villanova':          '#00205B',
  'Utah State':         '#0F2439',
  'Missouri':           '#F1B82D',
  'Texas':              '#BF5700',
  'NC State':           '#CC0000',
  'High Point':         '#330072',
  'Hawaii':             '#024731',
  'Kennesaw State':     '#FDBB30',
  'Queens':             '#002D62',
  'LIU':                '#003DA5',

  // Midwest Region
  'Michigan':           '#FFCB05',
  'Iowa State':         '#C8102E',
  'Virginia':           '#232D4B',
  'Alabama':            '#9E1B32',
  'Texas Tech':         '#CC0000',
  'Tennessee':          '#FF8200',
  'Kentucky':           '#0033A0',
  'Georgia':            '#BA0C2F',
  'Saint Louis':        '#003DA5',
  'Santa Clara':        '#862633',
  'Miami (OH)':         '#B61E2E',
  'SMU':                '#CC0000',
  'Akron':              '#041E42',
  'Hofstra':            '#003591',
  'Wright State':       '#007A33',
  'Tennessee State':    '#003DA5',
  'UMBC':               '#000000',
  'Howard':             '#003A63',
}

/** Default color for teams not in the mapping */
export const DEFAULT_TEAM_COLOR = '#475569'

/** Color for the "Rest" / "Other" pie slice */
export const REST_SLICE_COLOR = '#334155'

/**
 * Get team color by name, falling back to default.
 * @param {string} name - Team name exactly as returned by the API.
 * @returns {string} Hex color string.
 */
export function getTeamColor(name) {
  return TEAM_COLORS[name] || DEFAULT_TEAM_COLOR
}

export default TEAM_COLORS
