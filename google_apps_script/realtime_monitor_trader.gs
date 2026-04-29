const SPREADSHEET_ID = '1P5yQwn8K6aN62OTHRTyOlCKxTCedOXWVa8jiSFx87dU';
const CONFIG_SHEET = 'MonitorConfig';
const EVENTS_SHEET = 'MonitorEvents';
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
  'daily_change_pct',
  'signal',
  'reason',
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
  'paper_signal_enabled',
  'paper_position_size_pct',
  'stop_loss_pct',
  'take_profit_pct'
];

function setupMonitoringSheets() {
  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const config = getOrCreateSheet_(spreadsheet, CONFIG_SHEET);
  const events = getOrCreateSheet_(spreadsheet, EVENTS_SHEET);

  if (config.getLastRow() === 0) {
    config.appendRow(CONFIG_HEADERS);
    config.appendRow([true, 'NASDAQ:NVDA', 'Nvidia', '', '', 3, true, 0.03, 0.05, 0.10]);
    config.appendRow([true, 'NASDAQ:AAPL', 'Apple', '', '', 2, false, 0.02, 0.04, 0.08]);
    config.appendRow([true, 'NYSEARCA:SPY', 'S&P 500 ETF', '', '', 1.5, false, 0, 0, 0]);
  }

  if (events.getLastRow() === 0) {
    events.appendRow(EVENT_HEADERS);
  }
}

function runMonitoringCycle() {
  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const configSheet = getOrCreateSheet_(spreadsheet, CONFIG_SHEET);
  const eventsSheet = getOrCreateSheet_(spreadsheet, EVENTS_SHEET);
  ensureHeader_(eventsSheet, EVENT_HEADERS);

  const rows = readObjects_(configSheet);
  rows.forEach(row => {
    if (String(row.enabled).toLowerCase() !== 'true') {
      return;
    }

    const quote = fetchGoogleFinanceQuote_(spreadsheet, row.symbol);
    if (!quote || quote.price === null || quote.previousClose === null) {
      appendEvent_(eventsSheet, buildEvent_(row, quote, 'data_unavailable', 'low', 'Market data unavailable', '', ''));
      return;
    }

    const changePct = ((quote.price - quote.previousClose) / quote.previousClose) * 100;
    const threshold = Number(row.change_pct_abs || 0);
    const priceAbove = Number(row.price_above || 0);
    const priceBelow = Number(row.price_below || 0);

    if (threshold > 0 && Math.abs(changePct) >= threshold) {
      const severity = Math.abs(changePct) >= threshold * 2 ? 'high' : 'medium';
      const title = `${row.name || row.symbol} moved ${changePct.toFixed(2)}%`;
      appendEvent_(eventsSheet, buildEvent_(row, quote, 'price_alert', severity, title, '', `abs move >= ${threshold}%`));
    }

    if (priceAbove > 0 && quote.price >= priceAbove) {
      appendEvent_(eventsSheet, buildEvent_(row, quote, 'price_alert', 'medium', `${row.name || row.symbol} crossed above ${priceAbove}`, '', 'price_above'));
    }

    if (priceBelow > 0 && quote.price <= priceBelow) {
      appendEvent_(eventsSheet, buildEvent_(row, quote, 'price_alert', 'medium', `${row.name || row.symbol} crossed below ${priceBelow}`, '', 'price_below'));
    }

    if (String(row.paper_signal_enabled).toLowerCase() === 'true' && threshold > 0 && Math.abs(changePct) >= threshold) {
      const signal = changePct > 0 ? 'watch_pullback_entry' : 'watch_reversal_risk';
      const title = `Paper signal for ${row.name || row.symbol}: ${signal}`;
      appendEvent_(eventsSheet, buildEvent_(row, quote, 'paper_trade_signal', 'medium', title, signal, 'paper signal only; no live orders'));
    }
  });
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
    temp.getRange('A1').setFormula(`=GOOGLEFINANCE("${symbol}","price")`);
    temp.getRange('A2').setFormula(`=GOOGLEFINANCE("${symbol}","closeyest")`);
    SpreadsheetApp.flush();
    Utilities.sleep(2000);
    const price = Number(temp.getRange('A1').getValue());
    const previousClose = Number(temp.getRange('A2').getValue());
    return {
      price: Number.isFinite(price) ? price : null,
      previousClose: Number.isFinite(previousClose) ? previousClose : null
    };
  } finally {
    spreadsheet.deleteSheet(temp);
  }
}

function buildEvent_(row, quote, eventType, severity, title, signal, reason) {
  const now = new Date();
  const price = quote && quote.price !== null ? quote.price : '';
  const previousClose = quote && quote.previousClose !== null ? quote.previousClose : '';
  const changePct = price !== '' && previousClose !== '' ? ((price - previousClose) / previousClose) * 100 : '';
  const id = `${eventType}:${row.symbol}:${Utilities.formatDate(now, 'UTC', 'yyyyMMddHHmmss')}:${Math.random().toString(36).slice(2, 8)}`;

  return {
    id,
    source: SOURCE_NAME,
    event_type: eventType,
    symbol: row.symbol,
    severity,
    event_time: now.toISOString(),
    title,
    price,
    previous_close: previousClose,
    daily_change_pct: changePct === '' ? '' : changePct.toFixed(4),
    signal,
    reason,
    paper_position_size_pct: row.paper_position_size_pct || '',
    stop_loss_pct: row.stop_loss_pct || '',
    take_profit_pct: row.take_profit_pct || ''
  };
}

function appendEvent_(sheet, event) {
  ensureHeader_(sheet, EVENT_HEADERS);
  sheet.appendRow(EVENT_HEADERS.map(header => event[header] || ''));
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
