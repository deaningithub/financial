const SPREADSHEET_ID = '1IKQHRmyye8nXodRNNSYyo5QaCyJB8pYM4qUzg8tLwns';
const CONFIG_SHEET = 'MonitorConfig';
const EVENTS_SHEET = 'MonitorEvents';
const SNAPSHOT_SHEET = 'MonitorSnapshots';
const STATE_SHEET = 'MonitorState';
const SOURCE_NAME = 'google-apps-script-monitor';

const EVENT_HEADERS = [
  'id',
  'source',
  'event_type',
  'symbol',
  'severity',
  'event_time',
  'title',
  'price',
  'previous_close',
  'open',
  'day_high',
  'day_low',
  'volume',
  'market_cap',
  'trade_time',
  'data_delay_minutes',
  'daily_change_pct',
  'intraday_change_pct',
  'gap_pct',
  'signal',
  'reason',
  'threshold',
  'paper_position_size_pct',
  'stop_loss_pct',
  'take_profit_pct'
];

const CONFIG_HEADERS = [
  'enabled',
  'symbol',
  'name',
  'price_above',
  'price_below',
  'change_pct_abs',
  'intraday_change_pct_abs',
  'gap_pct_abs',
  'volume_above',
  'cooldown_minutes',
  'paper_signal_enabled',
  'paper_position_size_pct',
  'stop_loss_pct',
  'take_profit_pct'
];

const SNAPSHOT_HEADERS = [
  'last_checked',
  'symbol',
  'name',
  'price',
  'previous_close',
  'open',
  'day_high',
  'day_low',
  'volume',
  'market_cap',
  'trade_time',
  'data_delay_minutes',
  'daily_change_pct',
  'intraday_change_pct',
  'gap_pct',
  'status'
];

const STATE_HEADERS = [
  'event_key',
  'last_event_time',
  'symbol',
  'event_type',
  'reason'
];

function setupMonitoringSheets() {
  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const config = getOrCreateSheet_(spreadsheet, CONFIG_SHEET);
  const events = getOrCreateSheet_(spreadsheet, EVENTS_SHEET);
  const snapshots = getOrCreateSheet_(spreadsheet, SNAPSHOT_SHEET);
  const state = getOrCreateSheet_(spreadsheet, STATE_SHEET);

  ensureHeader_(config, CONFIG_HEADERS);
  if (config.getLastRow() === 1) {
    config.appendRow([true, 'NASDAQ:NVDA', 'Nvidia', '', '', 3, 2, 1.5, '', 60, true, 0.03, 0.05, 0.10]);
    config.appendRow([true, 'NASDAQ:AAPL', 'Apple', '', '', 2, 1.5, 1, '', 60, false, 0.02, 0.04, 0.08]);
    config.appendRow([true, 'NYSEARCA:SPY', 'S&P 500 ETF', '', '', 1.5, 1, 0.75, '', 60, false, 0, 0, 0]);
    config.appendRow([true, 'NASDAQ:QQQ', 'Nasdaq 100 ETF', '', '', 1.75, 1.25, 1, '', 60, false, 0, 0, 0]);
    config.appendRow([true, 'NYSEARCA:SMH', 'Semiconductor ETF', '', '', 2.5, 1.75, 1.25, '', 60, false, 0, 0, 0]);
    config.appendRow([true, 'NYSEARCA:TLT', '20Y Treasury ETF', '', '', 1.5, 1, 0.75, '', 60, false, 0, 0, 0]);
    config.appendRow([true, 'NYSEARCA:GLD', 'Gold ETF', '', '', 1.5, 1, 0.75, '', 60, false, 0, 0, 0]);
  }

  ensureHeader_(events, EVENT_HEADERS);
  ensureHeader_(snapshots, SNAPSHOT_HEADERS);
  ensureHeader_(state, STATE_HEADERS);
}

function runMonitoringCycle() {
  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const configSheet = getOrCreateSheet_(spreadsheet, CONFIG_SHEET);
  const eventsSheet = getOrCreateSheet_(spreadsheet, EVENTS_SHEET);
  const snapshotSheet = getOrCreateSheet_(spreadsheet, SNAPSHOT_SHEET);
  const stateSheet = getOrCreateSheet_(spreadsheet, STATE_SHEET);
  ensureHeader_(eventsSheet, EVENT_HEADERS);
  ensureHeader_(snapshotSheet, SNAPSHOT_HEADERS);
  ensureHeader_(stateSheet, STATE_HEADERS);

  const rows = readObjects_(configSheet);
  const state = readState_(stateSheet);
  const snapshots = [];
  rows.forEach(row => {
    if (String(row.enabled).toLowerCase() !== 'true') {
      return;
    }

    const quote = fetchGoogleFinanceQuote_(spreadsheet, row.symbol);
    snapshots.push(buildSnapshot_(row, quote));

    if (!quote || quote.price === null) {
      appendThrottledEvent_(eventsSheet, state, row, quote, 'data_unavailable', 'low', 'Market data unavailable', '', 'Market data unavailable', '');
      return;
    }

    const changePct = quote.dailyChangePct;
    const threshold = Number(row.change_pct_abs || 0);
    const intradayThreshold = Number(row.intraday_change_pct_abs || 0);
    const gapThreshold = Number(row.gap_pct_abs || 0);
    const volumeAbove = Number(row.volume_above || 0);
    const priceAbove = Number(row.price_above || 0);
    const priceBelow = Number(row.price_below || 0);

    if (threshold > 0 && Number.isFinite(changePct) && Math.abs(changePct) >= threshold) {
      const severity = severityForMove_(Math.abs(changePct), threshold);
      const title = `${row.name || row.symbol} moved ${changePct.toFixed(2)}%`;
      appendThrottledEvent_(eventsSheet, state, row, quote, 'price_alert', severity, title, '', `abs move >= ${threshold}%`, `${threshold}%`);
    }

    if (intradayThreshold > 0 && Number.isFinite(quote.intradayChangePct) && Math.abs(quote.intradayChangePct) >= intradayThreshold) {
      const severity = severityForMove_(Math.abs(quote.intradayChangePct), intradayThreshold);
      const title = `${row.name || row.symbol} intraday move ${quote.intradayChangePct.toFixed(2)}%`;
      appendThrottledEvent_(eventsSheet, state, row, quote, 'intraday_alert', severity, title, '', `intraday abs move >= ${intradayThreshold}%`, `${intradayThreshold}%`);
    }

    if (gapThreshold > 0 && Number.isFinite(quote.gapPct) && Math.abs(quote.gapPct) >= gapThreshold) {
      const severity = severityForMove_(Math.abs(quote.gapPct), gapThreshold);
      const title = `${row.name || row.symbol} opening gap ${quote.gapPct.toFixed(2)}%`;
      appendThrottledEvent_(eventsSheet, state, row, quote, 'gap_alert', severity, title, '', `gap abs move >= ${gapThreshold}%`, `${gapThreshold}%`);
    }

    if (volumeAbove > 0 && Number.isFinite(quote.volume) && quote.volume >= volumeAbove) {
      const title = `${row.name || row.symbol} volume above ${volumeAbove}`;
      appendThrottledEvent_(eventsSheet, state, row, quote, 'volume_alert', 'medium', title, '', 'volume_above', String(volumeAbove));
    }

    if (priceAbove > 0 && quote.price >= priceAbove) {
      appendThrottledEvent_(eventsSheet, state, row, quote, 'price_alert', 'medium', `${row.name || row.symbol} crossed above ${priceAbove}`, '', 'price_above', String(priceAbove));
    }

    if (priceBelow > 0 && quote.price <= priceBelow) {
      appendThrottledEvent_(eventsSheet, state, row, quote, 'price_alert', 'medium', `${row.name || row.symbol} crossed below ${priceBelow}`, '', 'price_below', String(priceBelow));
    }

    if (String(row.paper_signal_enabled).toLowerCase() === 'true' && threshold > 0 && Number.isFinite(changePct) && Math.abs(changePct) >= threshold) {
      const signal = changePct > 0 ? 'watch_pullback_entry' : 'watch_reversal_risk';
      const title = `Paper signal for ${row.name || row.symbol}: ${signal}`;
      appendThrottledEvent_(eventsSheet, state, row, quote, 'paper_trade_signal', 'medium', title, signal, 'paper signal only; no live orders', `${threshold}%`);
    }
  });
  writeSnapshots_(snapshotSheet, snapshots);
  writeState_(stateSheet, state);
}

function createTimeTrigger() {
  ScriptApp.newTrigger('runMonitoringCycle')
    .timeBased()
    .everyMinutes(15)
    .create();
}

function fetchGoogleFinanceQuote_(spreadsheet, symbol) {
  const temp = spreadsheet.insertSheet(`tmp_${Date.now()}`);
  try {
    const attributes = [
      ['price', 'A1'],
      ['closeyest', 'A2'],
      ['priceopen', 'A3'],
      ['high', 'A4'],
      ['low', 'A5'],
      ['volume', 'A6'],
      ['marketcap', 'A7'],
      ['tradetime', 'A8'],
      ['datadelay', 'A9']
    ];
    attributes.forEach(item => {
      temp.getRange(item[1]).setFormula(`=GOOGLEFINANCE("${symbol}","${item[0]}")`);
    });
    SpreadsheetApp.flush();
    Utilities.sleep(2000);
    const price = Number(temp.getRange('A1').getValue());
    const previousClose = Number(temp.getRange('A2').getValue());
    const open = Number(temp.getRange('A3').getValue());
    const high = Number(temp.getRange('A4').getValue());
    const low = Number(temp.getRange('A5').getValue());
    const volume = Number(temp.getRange('A6').getValue());
    const marketCap = Number(temp.getRange('A7').getValue());
    const tradeTime = temp.getRange('A8').getValue();
    const dataDelay = Number(temp.getRange('A9').getValue());
    const dailyChangePct = Number.isFinite(price) && Number.isFinite(previousClose) && previousClose !== 0
      ? ((price - previousClose) / previousClose) * 100
      : null;
    const intradayChangePct = Number.isFinite(price) && Number.isFinite(open) && open !== 0
      ? ((price - open) / open) * 100
      : null;
    const gapPct = Number.isFinite(open) && Number.isFinite(previousClose) && previousClose !== 0
      ? ((open - previousClose) / previousClose) * 100
      : null;
    return {
      price: Number.isFinite(price) ? price : null,
      previousClose: Number.isFinite(previousClose) ? previousClose : null,
      open: Number.isFinite(open) ? open : null,
      high: Number.isFinite(high) ? high : null,
      low: Number.isFinite(low) ? low : null,
      volume: Number.isFinite(volume) ? volume : null,
      marketCap: Number.isFinite(marketCap) ? marketCap : null,
      tradeTime: tradeTime instanceof Date ? tradeTime.toISOString() : String(tradeTime || ''),
      dataDelay: Number.isFinite(dataDelay) ? dataDelay : null,
      dailyChangePct,
      intradayChangePct,
      gapPct
    };
  } finally {
    spreadsheet.deleteSheet(temp);
  }
}

function buildEvent_(row, quote, eventType, severity, title, signal, reason, threshold) {
  const now = new Date();
  const id = `${eventType}:${row.symbol}:${Utilities.formatDate(now, 'UTC', 'yyyyMMddHHmmss')}:${Math.random().toString(36).slice(2, 8)}`;

  return {
    id,
    source: SOURCE_NAME,
    event_type: eventType,
    symbol: row.symbol,
    severity,
    event_time: now.toISOString(),
    title,
    price: formatMaybeNumber_(quote && quote.price),
    previous_close: formatMaybeNumber_(quote && quote.previousClose),
    open: formatMaybeNumber_(quote && quote.open),
    day_high: formatMaybeNumber_(quote && quote.high),
    day_low: formatMaybeNumber_(quote && quote.low),
    volume: formatMaybeNumber_(quote && quote.volume),
    market_cap: formatMaybeNumber_(quote && quote.marketCap),
    trade_time: quote && quote.tradeTime ? quote.tradeTime : '',
    data_delay_minutes: formatMaybeNumber_(quote && quote.dataDelay),
    daily_change_pct: formatMaybeNumber_(quote && quote.dailyChangePct, 4),
    intraday_change_pct: formatMaybeNumber_(quote && quote.intradayChangePct, 4),
    gap_pct: formatMaybeNumber_(quote && quote.gapPct, 4),
    signal,
    reason,
    threshold,
    paper_position_size_pct: row.paper_position_size_pct || '',
    stop_loss_pct: row.stop_loss_pct || '',
    take_profit_pct: row.take_profit_pct || ''
  };
}

function buildSnapshot_(row, quote) {
  const now = new Date().toISOString();
  return {
    last_checked: now,
    symbol: row.symbol,
    name: row.name || row.symbol,
    price: formatMaybeNumber_(quote && quote.price),
    previous_close: formatMaybeNumber_(quote && quote.previousClose),
    open: formatMaybeNumber_(quote && quote.open),
    day_high: formatMaybeNumber_(quote && quote.high),
    day_low: formatMaybeNumber_(quote && quote.low),
    volume: formatMaybeNumber_(quote && quote.volume),
    market_cap: formatMaybeNumber_(quote && quote.marketCap),
    trade_time: quote && quote.tradeTime ? quote.tradeTime : '',
    data_delay_minutes: formatMaybeNumber_(quote && quote.dataDelay),
    daily_change_pct: formatMaybeNumber_(quote && quote.dailyChangePct, 4),
    intraday_change_pct: formatMaybeNumber_(quote && quote.intradayChangePct, 4),
    gap_pct: formatMaybeNumber_(quote && quote.gapPct, 4),
    status: quote && quote.price !== null ? 'ok' : 'data_unavailable'
  };
}

function appendThrottledEvent_(sheet, state, row, quote, eventType, severity, title, signal, reason, threshold) {
  const eventKey = `${eventType}|${row.symbol}|${reason}|${threshold}`;
  const cooldownMinutes = Number(row.cooldown_minutes || 60);
  const lastEvent = state[eventKey] ? new Date(state[eventKey].last_event_time) : null;
  const now = new Date();
  if (lastEvent && cooldownMinutes > 0 && now.getTime() - lastEvent.getTime() < cooldownMinutes * 60 * 1000) {
    return;
  }
  appendEvent_(sheet, buildEvent_(row, quote, eventType, severity, title, signal, reason, threshold));
  state[eventKey] = {
    event_key: eventKey,
    last_event_time: now.toISOString(),
    symbol: row.symbol,
    event_type: eventType,
    reason
  };
}

function appendEvent_(sheet, event) {
  ensureHeader_(sheet, EVENT_HEADERS);
  sheet.appendRow(EVENT_HEADERS.map(header => event[header] || ''));
}

function writeSnapshots_(sheet, snapshots) {
  ensureHeader_(sheet, SNAPSHOT_HEADERS);
  if (sheet.getLastRow() > 1) {
    sheet.getRange(2, 1, sheet.getLastRow() - 1, SNAPSHOT_HEADERS.length).clearContent();
  }
  if (snapshots.length > 0) {
    sheet.getRange(2, 1, snapshots.length, SNAPSHOT_HEADERS.length)
      .setValues(snapshots.map(snapshot => SNAPSHOT_HEADERS.map(header => snapshot[header] || '')));
  }
}

function readState_(sheet) {
  const rows = readObjects_(sheet);
  const state = {};
  rows.forEach(row => {
    if (row.event_key) {
      state[row.event_key] = row;
    }
  });
  return state;
}

function writeState_(sheet, state) {
  ensureHeader_(sheet, STATE_HEADERS);
  if (sheet.getLastRow() > 1) {
    sheet.getRange(2, 1, sheet.getLastRow() - 1, STATE_HEADERS.length).clearContent();
  }
  const rows = Object.keys(state).sort().map(key => STATE_HEADERS.map(header => state[key][header] || ''));
  if (rows.length > 0) {
    sheet.getRange(2, 1, rows.length, STATE_HEADERS.length).setValues(rows);
  }
}

function severityForMove_(moveAbs, threshold) {
  return moveAbs >= threshold * 2 ? 'high' : 'medium';
}

function formatMaybeNumber_(value, digits) {
  if (!Number.isFinite(value)) {
    return '';
  }
  if (digits === undefined) {
    return value;
  }
  return value.toFixed(digits);
}

function readObjects_(sheet) {
  const values = sheet.getDataRange().getValues();
  if (values.length < 2) {
    return [];
  }
  const headers = values[0].map(value => String(value).trim());
  return values.slice(1).map(row => {
    const object = {};
    headers.forEach((header, index) => {
      object[header] = row[index];
    });
    return object;
  });
}

function ensureHeader_(sheet, headers) {
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(headers);
    return;
  }
  const current = sheet.getRange(1, 1, 1, headers.length).getValues()[0];
  if (current.join('|') !== headers.join('|')) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }
}

function getOrCreateSheet_(spreadsheet, name) {
  return spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);
}
