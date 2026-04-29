const TEST_SPREADSHEET_ID = '1P5yQwn8K6aN62OTHRTyOlCKxTCedOXWVa8jiSFx87dU';
const TEST_SHEET_NAME = 'ScriptTest';

function runSimpleSheetTest() {
  const spreadsheet = SpreadsheetApp.openById(TEST_SPREADSHEET_ID);
  const sheet = spreadsheet.getSheetByName(TEST_SHEET_NAME) || spreadsheet.insertSheet(TEST_SHEET_NAME);

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['timestamp', 'status', 'message']);
  }

  sheet.appendRow([
    new Date().toISOString(),
    'ok',
    'Google Apps Script test wrote to this sheet successfully.'
  ]);

  Logger.log('Simple sheet test completed.');
}
