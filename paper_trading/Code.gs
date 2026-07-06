// ============================================================
// PAPER TRADING APP - Google Apps Script
// IDX (Indonesian Stock Exchange) - Real-time Monitoring
// API: Yahoo Finance v8 | Trigger: 1 min (market hours only)
// Features: Bracket Orders (TP1/TP2/TP3 + SL), Long-only
// ============================================================

// ==================== CONFIGURATION ====================
var CONFIG = {
  SHEETS: {
    TRADE_LOG: 'Trade Log',
    PENDING: 'Pending Orders',
    DASHBOARD: 'Dashboard',
    SETTINGS: 'Settings',
    EQUITY: 'Equity Curve'
  },
  FEE: {
    BUY: 0.0015,
    SELL: 0.0025
  },
  MARKET: {
    OPEN_HOUR: 9,
    OPEN_MIN: 0,
    CLOSE_HOUR: 16,
    CLOSE_MIN: 1,
    LUNCH_START_HOUR: 12,
    LUNCH_END_HOUR: 13,
    TIMEZONE: 'Asia/Jakarta',
    // Friday lunch break hours (IDX specific)
    FRIDAY_SESSION1_END: 690,    // 11:30
    FRIDAY_SESSION2_START: 810,  // 13:30 (not 14:00)
    WEEKDAY_SESSION1_END: 720,   // 12:00
    WEEKDAY_SESSION2_START: 810, // 13:30
  },
  YAHOO: {
    BASE_URL: 'https://query1.finance.yahoo.com/v8/finance/chart/',
    BATCH_SIZE: 20,
    BATCH_PAUSE_MS: 1000
  },
  TRIGGER: {
    INTERVAL_MINUTES: 1
  },
  GAP: {
    TOLERANCE_PCT: 2.0
  }
};

// Trade Log columns (0-indexed):
// 0:TradeID 1:Date 2:Ticker 3:Qty 4:EntryPrice 5:EntryFee 6:EntryTotal
// 7:ExitDate 8:ExitPrice 9:ExitFee 10:ExitTotal
// 11:PnLRp 12:PnLPct 13:Status 14:RemainingQty 15:Strategy 16:Notes
var COL = {
  ID: 0, DATE: 1, TICKER: 2, QTY: 3, ENTRY: 4, ENTRY_FEE: 5, ENTRY_TOTAL: 6,
  EXIT_DATE: 7, EXIT_PRICE: 8, EXIT_FEE: 9, EXIT_TOTAL: 10,
  PNL_RP: 11, PNL_PCT: 12, STATUS: 13, REMAINING: 14, STRATEGY: 15, NOTES: 16
};

// Pending Orders columns (0-indexed):
// 0:OrderID 1:Date 2:Ticker 3:Type 4:Qty 5:TargetPrice 6:CurrentPrice
// 7:ChangePct 8:Status 9:ParentID 10:TPPct 11:Notes
var PCOL = {
  ID: 0, DATE: 1, TICKER: 2, TYPE: 3, QTY: 4, TARGET: 5, CURRENT: 6,
  CHANGE: 7, STATUS: 8, PARENT: 9, TP_PCT: 10, NOTES: 11
};

// ==================== UUID GENERATOR ====================
function generateTradeId() {
  var now = new Date();
  var mm = String(now.getMonth() + 1).padStart(2, '0');
  var dd = String(now.getDate()).padStart(2, '0');
  var hh = String(now.getHours()).padStart(2, '0');
  var mi = String(now.getMinutes()).padStart(2, '0');
  var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  var rand = '';
  for (var i = 0; i < 4; i++) {
    rand += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return 'T' + mm + dd + hh + mi + '_' + rand;
}

function generateOrderId() {
  var now = new Date();
  var mm = String(now.getMonth() + 1).padStart(2, '0');
  var dd = String(now.getDate()).padStart(2, '0');
  var hh = String(now.getHours()).padStart(2, '0');
  var mi = String(now.getMinutes()).padStart(2, '0');
  var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  var rand = '';
  for (var i = 0; i < 4; i++) {
    rand += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return 'P' + mm + dd + hh + mi + '_' + rand;
}

// ==================== ON OPEN ====================
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('📊 Paper Trading')
    .addSeparator()
    .addSubMenu(ui.createMenu('➕ Trade')
      .addItem('Open Trade', 'showOpenTradeForm')
      .addItem('Close Trade', 'showCloseTradeForm'))
    .addSeparator()
    .addSubMenu(ui.createMenu('📋 Pending Orders')
      .addItem('Add Pending Order', 'showPendingOrderForm')
      .addItem('Cancel Pending Order', 'cancelPendingOrder'))
    .addSeparator()
    .addItem('🔄 Refresh Prices Now', 'refreshPrices')
    .addItem('📈 Update Dashboard', 'updateDashboard')
    .addItem('📊 Generate Equity Curve', 'generateEquityCurve')
    .addSeparator()
    .addSubMenu(ui.createMenu('🤖 Auto Monitor')
      .addItem('Start (1 min)', 'createTrigger')
      .addItem('Stop', 'deleteTrigger')
      .addItem('Status', 'getTriggerStatus'))
    .addSeparator()
    .addSubMenu(ui.createMenu('🛠️ Tools')
      .addItem('📐 Position Calculator', 'calculatePositionSize')
      .addItem('📝 Trade Journal', 'addTradeJournal')
      .addItem('📋 Watchlist', 'showWatchlist')
      .addItem('📊 Daily Summary', 'sendDailySummary')
      .addItem('💾 Export CSV', 'exportToCSV'))
    .addSeparator()
    .addItem('⚙️ Settings', 'showSettings')
    .addItem('🔧 Setup Sheets', 'setupSheets')
    .addToUi();
}

// ==================== SETUP SHEETS ====================
function setupSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  // Sheet 1: Trade Log
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  if (!tradeLog) {
    tradeLog = ss.insertSheet(CONFIG.SHEETS.TRADE_LOG);
    tradeLog.appendRow([
      'Trade ID', 'Date', 'Ticker', 'Qty (lot)', 'Entry Price',
      'Entry Fee', 'Entry Total', 'Exit Date', 'Exit Price',
      'Exit Fee', 'Exit Total', 'P&L (Rp)', 'P&L (%)',
      'Status', 'Remaining Qty', 'Strategy', 'Notes'
    ]);
    tradeLog.getRange('1:1').setFontWeight('bold').setBackground('#4285F4').setFontColor('#FFFFFF');
    tradeLog.setFrozenRows(1);
    tradeLog.setColumnWidth(1, 80);
    tradeLog.setColumnWidth(2, 110);
    tradeLog.setColumnWidth(3, 80);
    tradeLog.setColumnWidth(4, 80);
    tradeLog.setColumnWidth(14, 90);
  }

  // Sheet 2: Pending Orders
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  if (!pending) {
    pending = ss.insertSheet(CONFIG.SHEETS.PENDING);
    pending.appendRow([
      'Order ID', 'Date', 'Ticker', 'Type', 'Qty (lot)',
      'Target Price', 'Current Price', 'Change %',
      'Status', 'Parent ID', 'TP %', 'Notes'
    ]);
    pending.getRange('1:1').setFontWeight('bold').setBackground('#FBBC04').setFontColor('#000000');
    pending.setFrozenRows(1);
    pending.setColumnWidth(1, 80);
    pending.setColumnWidth(2, 110);
    pending.setColumnWidth(4, 80);
    pending.setColumnWidth(9, 80);
    pending.setColumnWidth(10, 60);
  }

  // Sheet 3: Dashboard
  var dashboard = ss.getSheetByName(CONFIG.SHEETS.DASHBOARD);
  if (!dashboard) {
    dashboard = ss.insertSheet(CONFIG.SHEETS.DASHBOARD);
    dashboard.getRange('1:1').setBackground('#34A853').setFontColor('#FFFFFF').setFontWeight('bold');
    dashboard.getRange('A1').setValue('📊 PAPER TRADING DASHBOARD').setFontSize(14);
    dashboard.getRange('A2').setValue('Terakhir update:').setFontWeight('bold');
    dashboard.getRange('B2').setValue(new Date());
    dashboard.setColumnWidth(1, 180);
    dashboard.setColumnWidth(2, 150);
  }

  // Sheet 4: Settings
  var settings = ss.getSheetByName(CONFIG.SHEETS.SETTINGS);
  if (!settings) {
    settings = ss.insertSheet(CONFIG.SHEETS.SETTINGS);
    settings.getRange('1:1').setBackground('#999999').setFontColor('#FFFFFF').setFontWeight('bold');
    settings.getRange('A1').setValue('⚙️ SETTINGS').setFontSize(12);
    settings.getRange('A3:B3').setValues([['Parameter', 'Nilai']]).setFontWeight('bold');
    settings.getRange('A4:B9').setValues([
      ['Modal Awal', 100000000],
      ['Buy Fee', 0.0015],
      ['Sell Fee', 0.0025],
      ['Telegram Bot Token', ''],
      ['Telegram Chat ID', ''],
      ['Timezone', 'Asia/Jakarta']
    ]);
    settings.getRange('B5').setNumberFormat('0.00%');
    settings.getRange('B6').setNumberFormat('0.00%');
    settings.getRange('B7').setNumberFormat('@');  // Text format for Telegram token
    settings.getRange('A12').setValue('📋 TELEGRAM SETUP:').setFontWeight('bold');
    settings.getRange('A13:A20').setValues([
      ['1. Buka Telegram → cari @BotFather'],
      ['2. Kirim /newbot → ikuti instruksi'],
      ['3. Simpan Bot Token yang diberikan'],
      ['4. Kirim pesan ke bot Anda'],
      ['5. Buka: https://api.telegram.org/bot<TOKEN>/getUpdates'],
      ['6. Cari "chat":{"id": XXXXXXX} → itu Chat ID'],
      ['7. Masukkan Token dan Chat ID di atas (B7, B8)']
    ]);
    settings.setColumnWidth(1, 350);
    settings.setColumnWidth(2, 350);
  }

  // Sheet 5: Equity Curve
  var equity = ss.getSheetByName(CONFIG.SHEETS.EQUITY);
  if (!equity) {
    equity = ss.insertSheet(CONFIG.SHEETS.EQUITY);
    equity.appendRow(['Date', 'Total Equity', 'Modal', 'Return (%)']);
    equity.getRange('1:1').setFontWeight('bold').setBackground('#34A853').setFontColor('#FFFFFF');
    equity.setFrozenRows(1);
  }

  SpreadsheetApp.getUi().alert('✅ Sheets berhasil dibuat/diperiksa!');
}

// ==================== MARKET HOURS CHECK ====================
function isMarketOpen() {
  var now = new Date();
  var jakartaTime = Utilities.formatDate(now, CONFIG.MARKET.TIMEZONE, 'HH:mm');
  var jakartaDay = Utilities.formatDate(now, CONFIG.MARKET.TIMEZONE, 'EEEE');
  var h = parseInt(jakartaTime.split(':')[0]);
  var m = parseInt(jakartaTime.split(':')[1]);
  var t = h * 60 + m;

  if (jakartaDay === 'Saturday' || jakartaDay === 'Sunday') return false;

  var isFriday = (jakartaDay === 'Friday');
  var windows;
  if (isFriday) {
    windows = [[530, 690], [840, 971]];  // 08:50-11:30, 14:00-16:11
  } else {
    windows = [[530, 720], [810, 971]];  // 08:50-12:00, 13:30-16:11
  }

  for (var i = 0; i < windows.length; i++) {
    if (t >= windows[i][0] && t <= windows[i][1]) return true;
  }
  return false;
}

// ==================== YAHOO FINANCE API ====================
function getIDXPrice(ticker) {
  var symbol = ticker.indexOf('.JK') > -1 ? ticker : ticker + '.JK';
  var url = CONFIG.YAHOO.BASE_URL + symbol + '?interval=1m&range=1d';
  var options = {
    'method': 'GET',
    'headers': { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
    'muteHttpExceptions': true
  };

  try {
    var response = UrlFetchApp.fetch(url, options);
    if (response.getResponseCode() !== 200) return { error: 'HTTP ' + response.getResponseCode() };
    var json = JSON.parse(response.getContentText());
    var result = json.chart.result;
    if (!result || result.length === 0) return { error: 'No data' };
    var meta = result[0].meta;
    var price = meta.regularMarketPrice;
    var prevClose = meta.chartPreviousClose;
    return {
      price: price, high: meta.regularMarketDayHigh, low: meta.regularMarketDayLow,
      volume: meta.regularMarketVolume, prevClose: prevClose,
      change: price - prevClose,
      changePct: prevClose ? ((price - prevClose) / prevClose * 100).toFixed(2) : '0.00',
      currency: meta.currency, name: meta.shortName || ticker
    };
  } catch (e) {
    return { error: e.toString() };
  }
}

function getIDXPriceFallback(ticker) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEETS.TRADE_LOG);
    var cell = sheet.getRange('ZZ1');
    cell.setFormula('=GOOGLEFINANCE("' + ticker + '.JK", "price")');
    Utilities.sleep(1000);
    var val = cell.getValue();
    cell.clear();
    return { price: val, source: 'GOOGLEFINANCE' };
  } catch (e) {
    return { error: 'All sources failed: ' + e.toString() };
  }
}

function getIDXPricesBatch(tickers) {
  var results = {};
  for (var i = 0; i < tickers.length; i++) {
    results[tickers[i]] = getIDXPrice(tickers[i]);
    if ((i + 1) % CONFIG.YAHOO.BATCH_SIZE === 0 && i < tickers.length - 1) {
      Utilities.sleep(CONFIG.YAHOO.BATCH_PAUSE_MS);
    }
  }
  return results;
}

// ==================== TRADE FUNCTIONS ====================
function openTradeManual() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var lastRow = tradeLog.getLastRow();
  var tradeId = generateTradeId();
  var ui = SpreadsheetApp.getUi();

  var ticker = ui.prompt('Ticker (tanpa .JK)', 'Contoh: BBCA', ui.ButtonSet.OK_CANCEL);
  if (ticker.getSelectedButton() !== ui.Button.OK) return;
  var tickerVal = ticker.getResponseText().toUpperCase().trim();

  var qty = ui.prompt('Qty (lot)', 'Contoh: 10', ui.ButtonSet.OK_CANCEL);
  if (qty.getSelectedButton() !== ui.Button.OK) return;
  var qtyVal = parseInt(qty.getResponseText());

  var price = ui.prompt('Entry Price', 'Contoh: 9500', ui.ButtonSet.OK_CANCEL);
  if (price.getSelectedButton() !== ui.Button.OK) return;
  var priceVal = parseFloat(price.getResponseText());

  if (!tickerVal || !qtyVal || !priceVal) { ui.alert('❌ Semua field harus diisi!'); return; }

  var entryTotal = priceVal * qtyVal * 100;
  var entryFee = entryTotal * CONFIG.FEE.BUY;

  var now = new Date();
  tradeLog.appendRow([
    tradeId, now, tickerVal, qtyVal, priceVal, entryFee, entryTotal + entryFee,
    '', '', '', '', '', '', 'OPEN', qtyVal, '', ''
  ]);

  var row = tradeLog.getLastRow();
  tradeLog.getRange(row, 1, 1, tradeLog.getLastColumn()).setBackground('#E6F4EA');
  tradeLog.getRange(row, COL.STATUS + 1).setFontWeight('bold');

  ui.alert('✅ Trade Opened!\n\nID: ' + tradeId + '\nTicker: ' + tickerVal + '\nQty: ' + qtyVal + ' lot @ Rp ' + priceVal.toLocaleString());
}

function closeTradeManual() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var ui = SpreadsheetApp.getUi();
  var data = tradeLog.getDataRange().getValues();
  var openTrades = [];

  for (var i = 1; i < data.length; i++) {
    if (data[i][COL.STATUS] === 'OPEN' || data[i][COL.STATUS] === 'PARTIAL') {
      openTrades.push({
        row: i + 1, id: data[i][COL.ID], ticker: data[i][COL.TICKER],
        qty: data[i][COL.QTY], entryPrice: data[i][COL.ENTRY],
        remaining: data[i][COL.REMAINING]
      });
    }
  }

  if (openTrades.length === 0) { ui.alert('Tidak ada trade OPEN/PARTIAL.'); return; }

  var list = openTrades.map(function(t) {
    return t.id + ' | ' + t.ticker + ' | ' + t.remaining + '/' + t.qty + ' lots @ Rp ' + t.entryPrice;
  }).join('\n');

  var choice = ui.prompt('Pilih Trade ID:\n\n' + list, 'Trade ID', ui.ButtonSet.OK_CANCEL);
  if (choice.getSelectedButton() !== ui.Button.OK) return;
  var tradeId = choice.getResponseText().toUpperCase().trim();
  var trade = openTrades.find(function(t) { return t.id === tradeId; });
  if (!trade) { ui.alert('❌ Trade ID tidak ditemukan!'); return; }

  var exitPrice = ui.prompt('Exit Price (' + trade.ticker + ')\nRemaining: ' + trade.remaining + ' lots', 'Contoh: 9800', ui.ButtonSet.OK_CANCEL);
  if (exitPrice.getSelectedButton() !== ui.Button.OK) return;
  var exitVal = parseFloat(exitPrice.getResponseText());

  var closeQty = trade.remaining;
  var originalQty = parseInt(data[trade.row - 1][COL.QTY]);
  var entryTotal = parseFloat(data[trade.row - 1][COL.ENTRY_TOTAL]);
  var exitTotal = exitVal * closeQty * 100;
  var exitFee = exitTotal * CONFIG.FEE.SELL;
  var pnl = (exitTotal - exitFee) - (entryTotal * closeQty / originalQty);
  var pnlPct = (exitVal - parseFloat(data[trade.row - 1][COL.ENTRY])) / parseFloat(data[trade.row - 1][COL.ENTRY]) * 100;
  var newRemaining = 0;
  var newStatus = 'CLOSED';

  var row = trade.row;
  var now = new Date();
  tradeLog.getRange(row, COL.EXIT_DATE + 1).setValue(now);
  tradeLog.getRange(row, COL.EXIT_PRICE + 1).setValue(exitVal);
  tradeLog.getRange(row, COL.EXIT_FEE + 1).setValue(exitFee);
  tradeLog.getRange(row, COL.EXIT_TOTAL + 1).setValue(exitTotal - exitFee);
  tradeLog.getRange(row, COL.PNL_RP + 1).setValue(pnl);
  tradeLog.getRange(row, COL.PNL_PCT + 1).setValue(pnlPct);
  tradeLog.getRange(row, COL.STATUS + 1).setValue(newStatus).setFontWeight('bold');
  tradeLog.getRange(row, COL.REMAINING + 1).setValue(newRemaining);

  tradeLog.getRange(row, COL.PNL_RP + 1).setBackground(pnl >= 0 ? '#E6F4EA' : '#FCE8E6');
  tradeLog.getRange(row, COL.PNL_PCT + 1).setBackground(pnl >= 0 ? '#E6F4EA' : '#FCE8E6');

  var notes = data[trade.row - 1][COL.NOTES] || '';
  var match = notes.match(/Auto-matched from (P[A-Z0-9_]+)/);
  if (match) cancelPendingByParent(match[1]);
  else {
    // Find parent ID from Pending Orders for this ticker
    var parentId = findParentIdForTicker(trade.ticker);
    if (parentId) cancelPendingByParent(parentId);
  }

  ui.alert('✅ Trade Closed!\n\n' + tradeId + ' | ' + trade.ticker +
    '\nP&L: Rp ' + pnl.toLocaleString() + '\nReturn: ' + pnlPct.toFixed(2) + '%');
}

// ==================== PENDING ORDER FUNCTIONS ====================
function addPendingOrder() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var ui = SpreadsheetApp.getUi();
  var lastRow = pending.getLastRow();
  var orderId = generateOrderId();

  var ticker = ui.prompt('Ticker (tanpa .JK)', 'Contoh: BBCA', ui.ButtonSet.OK_CANCEL);
  if (ticker.getSelectedButton() !== ui.Button.OK) return;
  var tickerVal = ticker.getResponseText().toUpperCase().trim();

  var qty = ui.prompt('Qty (lot)', 'Contoh: 10', ui.ButtonSet.OK_CANCEL);
  if (qty.getSelectedButton() !== ui.Button.OK) return;
  var qtyVal = parseInt(qty.getResponseText());

  var entryPrice = ui.prompt('Entry Price', 'Contoh: 9500', ui.ButtonSet.OK_CANCEL);
  if (entryPrice.getSelectedButton() !== ui.Button.OK) return;
  var entryVal = parseFloat(entryPrice.getResponseText());

  var tp1Price = ui.prompt('Take Profit 1 Price', 'Contoh: 10000', ui.ButtonSet.OK_CANCEL);
  if (tp1Price.getSelectedButton() !== ui.Button.OK) return;
  var tp1Val = parseFloat(tp1Price.getResponseText());
  var tp1Pct = ui.prompt('TP 1 Qty %', 'Contoh: 50', ui.ButtonSet.OK_CANCEL);
  if (tp1Pct.getSelectedButton() !== ui.Button.OK) return;
  var tp1PctVal = parseInt(tp1Pct.getResponseText());

  var tp2Price = ui.prompt('Take Profit 2 Price', 'Contoh: 10500', ui.ButtonSet.OK_CANCEL);
  if (tp2Price.getSelectedButton() !== ui.Button.OK) return;
  var tp2Val = parseFloat(tp2Price.getResponseText());
  var tp2Pct = ui.prompt('TP 2 Qty %', 'Contoh: 30', ui.ButtonSet.OK_CANCEL);
  if (tp2Pct.getSelectedButton() !== ui.Button.OK) return;
  var tp2PctVal = parseInt(tp2Pct.getResponseText());

  var tp3Price = ui.prompt('Take Profit 3 Price', 'Contoh: 11000', ui.ButtonSet.OK_CANCEL);
  if (tp3Price.getSelectedButton() !== ui.Button.OK) return;
  var tp3Val = parseFloat(tp3Price.getResponseText());
  var tp3Pct = 100 - tp1PctVal - tp2PctVal;

  var slPrice = ui.prompt('Stop Loss Price', 'Contoh: 9000', ui.ButtonSet.OK_CANCEL);
  if (slPrice.getSelectedButton() !== ui.Button.OK) return;
  var slVal = parseFloat(slPrice.getResponseText());

  if (!tickerVal || !qtyVal || !entryVal || !tp1Val || !tp2Val || !tp3Val || !slVal) {
    ui.alert('❌ Semua field harus diisi!');
    return;
  }
  if (tp1PctVal + tp2PctVal + tp3PctVal !== 100) {
    ui.alert('❌ Total TP % harus 100%! (TP1: ' + tp1PctVal + '% + TP2: ' + tp2PctVal + '% + TP3: ' + tp3PctVal + '% = ' + (tp1PctVal + tp2PctVal + tp3PctVal) + '%)');
    return;
  }

  var now = new Date();
  var livePrice = getIDXPrice(tickerVal);
  var currentPrice = livePrice.price || 0;

  pending.appendRow([
    orderId, now, tickerVal, 'BUY', qtyVal, entryVal, currentPrice,
    currentPrice ? ((currentPrice - entryVal) / entryVal * 100).toFixed(2) : '0.00',
    'PENDING', '', '', ''
  ]);
  var buyRow = pending.getLastRow();
  pending.getRange(buyRow, 1, 1, pending.getLastColumn()).setBackground('#E6F4EA');
  pending.getRange(buyRow, PCOL.STATUS + 1).setFontWeight('bold');

  var tp1Qty = Math.round(qtyVal * tp1PctVal / 100);
  var tp2Qty = Math.round(qtyVal * tp2PctVal / 100);
  var tp3Qty = qtyVal - tp1Qty - tp2Qty;

  var tp1Id = generateOrderId();
  pending.appendRow([
    tp1Id, now, tickerVal, 'SELL', tp1Qty, tp1Val, currentPrice,
    currentPrice ? ((currentPrice - tp1Val) / tp1Val * 100).toFixed(2) : '0.00',
    'PENDING', orderId, tp1PctVal + '%', ''
  ]);
  pending.getRange(pending.getLastRow(), 1, 1, pending.getLastColumn()).setBackground('#FCE8E6');

  var tp2Id = generateOrderId();
  pending.appendRow([
    tp2Id, now, tickerVal, 'SELL', tp2Qty, tp2Val, currentPrice,
    currentPrice ? ((currentPrice - tp2Val) / tp2Val * 100).toFixed(2) : '0.00',
    'PENDING', orderId, tp2PctVal + '%', ''
  ]);
  pending.getRange(pending.getLastRow(), 1, 1, pending.getLastColumn()).setBackground('#FCE8E6');

  var tp3Id = generateOrderId();
  pending.appendRow([
    tp3Id, now, tickerVal, 'SELL', tp3Qty, tp3Val, currentPrice,
    currentPrice ? ((currentPrice - tp3Val) / tp3Val * 100).toFixed(2) : '0.00',
    'PENDING', orderId, tp3PctVal + '%', ''
  ]);
  pending.getRange(pending.getLastRow(), 1, 1, pending.getLastColumn()).setBackground('#FCE8E6');

  var slId = generateOrderId();
  pending.appendRow([
    slId, now, tickerVal, 'STOPLOSS', qtyVal, slVal, currentPrice,
    currentPrice ? ((currentPrice - slVal) / slVal * 100).toFixed(2) : '0.00',
    'PENDING', orderId, '100%', ''
  ]);
  pending.getRange(pending.getLastRow(), 1, 1, pending.getLastColumn()).setBackground('#FDD663');

  ui.alert('✅ Bracket Order Created!\n\n' + orderId + ' | ' + tickerVal +
    '\nEntry: ' + qtyVal + ' lots @ Rp ' + entryVal.toLocaleString() +
    '\nTP1: ' + tp1Qty + ' lots @ Rp ' + tp1Val.toLocaleString() + ' (' + tp1PctVal + '%)' +
    '\nTP2: ' + tp2Qty + ' lots @ Rp ' + tp2Val.toLocaleString() + ' (' + tp2PctVal + '%)' +
    '\nTP3: ' + tp3Qty + ' lots @ Rp ' + tp3Val.toLocaleString() + ' (' + tp3PctVal + '%)' +
    '\nSL: ' + qtyVal + ' lots @ Rp ' + slVal.toLocaleString());
}

function cancelPendingOrder() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var ui = SpreadsheetApp.getUi();
  var data = pending.getDataRange().getValues();
  var pendingOrders = [];

  for (var i = 1; i < data.length; i++) {
    if (data[i][PCOL.STATUS] === 'PENDING') {
      pendingOrders.push({
        row: i + 1, id: data[i][PCOL.ID], ticker: data[i][PCOL.TICKER],
        type: data[i][PCOL.TYPE], target: data[i][PCOL.TARGET]
      });
    }
  }

  if (pendingOrders.length === 0) { ui.alert('Tidak ada pending order.'); return; }

  var list = pendingOrders.map(function(o) {
    return o.id + ' | ' + o.ticker + ' | ' + o.type + ' | Target: Rp ' + o.target;
  }).join('\n');

  var choice = ui.prompt('Pilih Order ID:\n\n' + list, 'Order ID', ui.ButtonSet.OK_CANCEL);
  if (choice.getSelectedButton() !== ui.Button.OK) return;
  var orderId = choice.getResponseText().toUpperCase().trim();
  var order = pendingOrders.find(function(o) { return o.id === orderId; });
  if (!order) { ui.alert('❌ Order ID tidak ditemukan!'); return; }

  pending.getRange(order.row, PCOL.STATUS + 1).setValue('CANCELLED');
  pending.getRange(order.row, PCOL.STATUS + 1).setBackground('#FDD663');
  ui.alert('✅ Order ' + orderId + ' dibatalkan.');
}

function cancelPendingByParent(parentId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var data = pending.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    // Cancel parent BUY order (ID matches) atau child orders (PARENT matches)
    var isParent = data[i][PCOL.ID] === parentId && data[i][PCOL.STATUS] === 'PENDING';
    var isChild = data[i][PCOL.PARENT] === parentId && data[i][PCOL.STATUS] === 'PENDING';
    if (isParent || isChild) {
      pending.getRange(i + 1, PCOL.STATUS + 1).setValue('CANCELLED');
      pending.getRange(i + 1, PCOL.STATUS + 1).setBackground('#FDD663');
    }
  }
}

function findParentIdForTicker(ticker) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var data = pending.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][PCOL.TICKER] === ticker && data[i][PCOL.TYPE] === 'BUY' && data[i][PCOL.STATUS] === 'PENDING') {
      return data[i][PCOL.ID];
    }
  }
  return null;
}

function getParentStatus(pData, parentId) {
  for (var j = 1; j < pData.length; j++) {
    if (pData[j][PCOL.ID] === parentId) {
      return pData[j][PCOL.STATUS];
    }
  }
  return null;
}

// ==================== GAP DETECTION ====================
function checkGapAndCancel() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var data = pending.getDataRange().getValues();
  var cancelled = [];

  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    var status = row[PCOL.STATUS];
    var type = row[PCOL.TYPE];
    var ticker = row[PCOL.TICKER];
    var target = parseFloat(row[PCOL.TARGET]);
    var current = parseFloat(row[PCOL.CURRENT]);

    // Only check PENDING BUY orders
    if (status !== 'PENDING' || type !== 'BUY' || !target || !current || isNaN(target) || isNaN(current)) continue;

    // Calculate gap: (current - target) / target * 100
    var gapPct = ((current - target) / target) * 100;

    // If gap > tolerance, cancel entire bracket order
    if (gapPct > CONFIG.GAP.TOLERANCE_PCT) {
      var orderId = row[PCOL.ID];
      cancelPendingByParent(orderId);
      cancelled.push({
        ticker: ticker,
        target: target,
        current: current,
        gap: gapPct.toFixed(1)
      });
      Logger.log('GAP CANCEL: ' + ticker + ' target=' + target + ' current=' + current + ' gap=' + gapPct.toFixed(1) + '%');
    }
  }

  // Send Telegram alert if any orders cancelled
  if (cancelled.length > 0) {
    var msg = '⚠️ GAP UP DETECTED — Orders Cancelled:\n';
    for (var j = 0; j < cancelled.length; j++) {
      var c = cancelled[j];
      msg += '• ' + c.ticker + ': target Rp ' + c.target + ' → current Rp ' + c.current + ' (gap ' + c.gap + '%)\n';
    }
    msg += '\nTunggu pullback atau near entry zone.';
    sendTelegram(msg);
  }

  return cancelled;
}

// ==================== PRICE MONITORING ====================
function refreshPrices() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var tickers = new Set();

  var pData = pending.getDataRange().getValues();
  for (var i = 1; i < pData.length; i++) {
    if (pData[i][PCOL.TICKER]) tickers.add(pData[i][PCOL.TICKER]);
  }
  var tData = tradeLog.getDataRange().getValues();
  for (var j = 1; j < tData.length; j++) {
    if (tData[j][COL.STATUS] === 'OPEN' || tData[j][COL.STATUS] === 'PARTIAL') {
      tickers.add(tData[j][COL.TICKER]);
    }
  }

  if (tickers.size === 0) { Logger.log('No tickers to refresh.'); return; }

  var tickerArray = Array.from(tickers);
  Logger.log('Fetching prices for: ' + tickerArray.join(', '));

  var prices = {};
  var successCount = 0, failCount = 0, fallbackCount = 0;
  for (var i = 0; i < tickerArray.length; i++) {
    var ticker = tickerArray[i];
    var result = getIDXPrice(ticker);

    if (result && result.price) {
      prices[ticker] = result;
      successCount++;
    } else {
      Logger.log('Yahoo Finance failed for ' + ticker + ': ' + (result.error || 'No price') + ' → Trying GOOGLEFINANCE...');
      var fallback = getIDXPriceFallback(ticker);
      if (fallback && fallback.price) {
        prices[ticker] = fallback;
        fallbackCount++;
        Logger.log('GOOGLEFINANCE fallback OK for ' + ticker + ': Rp ' + fallback.price);
      } else {
        failCount++;
        Logger.log('All sources failed for ' + ticker);
      }
    }

    if ((i + 1) % CONFIG.YAHOO.BATCH_SIZE === 0 && i < tickerArray.length - 1) {
      Utilities.sleep(CONFIG.YAHOO.BATCH_PAUSE_MS);
    }
  }

  var updated = 0;
  for (var k = 1; k < pData.length; k++) {
    if (pData[k][PCOL.TICKER]) {
      var ticker = pData[k][PCOL.TICKER];
      var priceData = prices[ticker];
      if (priceData && priceData.price) {
        var target = parseFloat(pData[k][PCOL.TARGET]);
        var current = priceData.price;
        var changePct = ((current - target) / target * 100).toFixed(2);
        pending.getRange(k + 1, PCOL.CURRENT + 1).setValue(current);
        pending.getRange(k + 1, PCOL.CHANGE + 1).setValue(changePct);

        var proximity = Math.abs(current - target) / target * 100;
        if (proximity < 1) pending.getRange(k + 1, PCOL.CURRENT + 1).setBackground('#FDD663');
        else if (proximity < 3) pending.getRange(k + 1, PCOL.CURRENT + 1).setBackground('#FCE8E6');
        else pending.getRange(k + 1, PCOL.CURRENT + 1).setBackground('#FFFFFF');
        updated++;
      }
    }
  }

  Logger.log('Price refresh: ' + successCount + ' OK, ' + fallbackCount + ' fallback, ' + failCount + ' failed, ' + updated + ' rows updated.');
}

// ==================== CORE: CHECK PENDING ORDERS ====================
function checkPendingOrders() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var pData = pending.getDataRange().getValues();
  var tData = tradeLog.getDataRange().getValues();
  var matchedCount = 0;

  for (var i = 1; i < pData.length; i++) {
    if (pData[i][PCOL.STATUS] !== 'PENDING') continue;

    var ticker = pData[i][PCOL.TICKER];
    var type = pData[i][PCOL.TYPE];
    var qty = parseInt(pData[i][PCOL.QTY]);
    var target = parseFloat(pData[i][PCOL.TARGET]);
    var current = parseFloat(pData[i][PCOL.CURRENT]);
    var parentId = pData[i][PCOL.PARENT];

    if (!current || !target) continue;

    // Parent status check: SELL/STOPLOSS hanya boleh match jika parent BUY sudah MATCHED
    if ((type === 'SELL' || type === 'STOPLOSS') && parentId) {
      var parentStatus = getParentStatus(pData, parentId);
      if (parentStatus !== 'MATCHED') {
        continue; // Skip — parent BUY belum matched
      }
    }

    var matched = false;
    if (type === 'BUY' && current <= target) matched = true;
    if (type === 'SELL' && current >= target) matched = true;
    if (type === 'STOPLOSS' && current <= target) matched = true;

    if (matched) {
      matchedCount++;
      pending.getRange(i + 1, PCOL.STATUS + 1).setValue('MATCHED');
      pending.getRange(i + 1, PCOL.STATUS + 1).setBackground('#34A853').setFontColor('#FFFFFF');

      if (type === 'BUY') {
        var tradeId = generateTradeId();
        var entryTotal = current * qty * 100;
        var entryFee = entryTotal * CONFIG.FEE.BUY;
        var now = new Date();
        tradeLog.appendRow([
          tradeId, now, ticker, qty, current, entryFee, entryTotal + entryFee,
          '', '', '', '', '', '', 'OPEN', qty, '', 'Auto-matched from ' + pData[i][PCOL.ID]
        ]);
        var tradeRow = tradeLog.getLastRow();
        tradeLog.getRange(tradeRow, 1, 1, tradeLog.getLastColumn()).setBackground('#E6F4EA');
        tradeLog.getRange(tradeRow, COL.STATUS + 1).setFontWeight('bold');

        var msg = '🔔 BUY MATCHED!\n\n📊 ' + ticker + '\n💰 Entry: Rp ' + current.toLocaleString() + ' × ' + qty + ' lots\n📦 Trade ID: ' + tradeId +
          '\n⏰ ' + Utilities.formatDate(now, CONFIG.MARKET.TIMEZONE, 'dd MMM yyyy, HH:mm') + ' WIB';
        sendTelegram(msg);

      } else if (type === 'SELL' || type === 'STOPLOSS') {
        // Collect all matching trades for this ticker
        var matchedTrades = [];
        for (var t2 = 1; t2 < tData.length; t2++) {
          if (tData[t2][COL.TICKER] === ticker && (tData[t2][COL.STATUS] === 'OPEN' || tData[t2][COL.STATUS] === 'PARTIAL')) {
            matchedTrades.push(t2);
          }
        }

        // Try to match by Parent ID first (from Notes field)
        var bestMatch = -1;
        if (parentId) {
          for (var m = 0; m < matchedTrades.length; m++) {
            var t2 = matchedTrades[m];
            if (tData[t2][COL.NOTES].indexOf(parentId) > -1) {
              bestMatch = t2;
              break;
            }
          }
        }

        // Fallback: match oldest OPEN trade for this ticker (manual trades)
        if (bestMatch === -1 && matchedTrades.length > 0) {
          bestMatch = matchedTrades[0];
        }

        if (bestMatch >= 0) {
          var t2 = bestMatch;
          var tradeRow2 = t2 + 1;
          var tradeId2 = tData[t2][COL.ID];
          var remaining = parseInt(tData[t2][COL.REMAINING]);
          var entryTotal2 = parseFloat(tData[t2][COL.ENTRY_TOTAL]);
          var closeQty = Math.min(qty, remaining);

          var exitTotal = current * closeQty * 100;
          var exitFee = exitTotal * CONFIG.FEE.SELL;
          var totalQty = parseInt(tData[t2][COL.QTY]);
          var entryFee2 = parseFloat(tData[t2][COL.ENTRY_FEE]);
          var costBasisPerLot = (entryTotal2 - entryFee2) / totalQty;
          var proportionalEntryFee = entryFee2 * closeQty / totalQty;
          var costBasis = costBasisPerLot * closeQty + proportionalEntryFee;
          var pnl = (exitTotal - exitFee) - costBasis;
          var pnlPct = (current - parseFloat(tData[t2][COL.ENTRY])) / parseFloat(tData[t2][COL.ENTRY]) * 100;

          tradeLog.getRange(tradeRow2, COL.EXIT_DATE + 1).setValue(new Date());
          tradeLog.getRange(tradeRow2, COL.EXIT_PRICE + 1).setValue(current);
          tradeLog.getRange(tradeRow2, COL.EXIT_FEE + 1).setValue(exitFee);
          tradeLog.getRange(tradeRow2, COL.EXIT_TOTAL + 1).setValue(exitTotal - exitFee);
          tradeLog.getRange(tradeRow2, COL.PNL_RP + 1).setValue(pnl);
          tradeLog.getRange(tradeRow2, COL.PNL_PCT + 1).setValue(pnlPct);

          var newRemaining = remaining - closeQty;
          tradeLog.getRange(tradeRow2, COL.REMAINING + 1).setValue(newRemaining);
          var newStatus = newRemaining <= 0 ? 'CLOSED' : 'PARTIAL';
          tradeLog.getRange(tradeRow2, COL.STATUS + 1).setValue(newStatus).setFontWeight('bold');

          // Update tData in-memory to prevent stale data for subsequent matches
          tData[t2][COL.REMAINING] = newRemaining;
          tData[t2][COL.STATUS] = newStatus;
          tData[t2][COL.EXIT_DATE] = new Date();
          tData[t2][COL.EXIT_PRICE] = current;
          tData[t2][COL.PNL_RP] = pnl;
          tData[t2][COL.PNL_PCT] = pnlPct;

          tradeLog.getRange(tradeRow2, COL.PNL_RP + 1).setBackground(pnl >= 0 ? '#E6F4EA' : '#FCE8E6');
          tradeLog.getRange(tradeRow2, COL.PNL_PCT + 1).setBackground(pnl >= 0 ? '#E6F4EA' : '#FCE8E6');

          var label = type === 'STOPLOSS' ? 'STOP LOSS' : 'TAKE PROFIT';
          var pctLabel = pData[i][PCOL.TP_PCT] ? ' (' + pData[i][PCOL.TP_PCT] + ')' : '';
          var statusLabel = newStatus === 'CLOSED' ? ' - ALL DONE!' : '';

          var msg2 = '🔔 ' + label + ' MATCHED!' + pctLabel + statusLabel + '\n\n📊 ' + ticker +
            '\n✅ Closed: ' + closeQty + ' lots @ Rp ' + current.toLocaleString() +
            '\n💰 P&L: Rp ' + pnl.toLocaleString() + ' (' + pnlPct.toFixed(2) + '%)' +
            '\n📦 Remaining: ' + newRemaining + ' lots' +
            '\n⏰ ' + Utilities.formatDate(new Date(), CONFIG.MARKET.TIMEZONE, 'dd MMM yyyy, HH:mm') + ' WIB';
          sendTelegram(msg2);

          if (newRemaining <= 0 && parentId) cancelPendingByParent(parentId);
          // Also cancel remaining TPs when STOPLOSS closes the trade
          if (type === 'STOPLOSS' && parentId) cancelPendingByParent(parentId);
        }
      }
    }
  }

  if (matchedCount > 0) Logger.log('Total matched: ' + matchedCount + ' orders');
}

// ==================== TELEGRAM INTEGRATION ====================
function sendTelegram(message) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var settings = ss.getSheetByName(CONFIG.SHEETS.SETTINGS);
  var botToken = settings.getRange('B7').getValue();
  var chatId = settings.getRange('B8').getValue();
  if (!botToken || !chatId) { Logger.log('Telegram not configured.'); return false; }

  var url = 'https://api.telegram.org/bot' + botToken + '/sendMessage';
  var payload = { 'chat_id': chatId, 'text': message };
  var options = {
    'method': 'POST', 'contentType': 'application/json',
    'payload': JSON.stringify(payload), 'muteHttpExceptions': true
  };

  try {
    var response = UrlFetchApp.fetch(url, options);
    var result = JSON.parse(response.getContentText());
    if (result.ok) { Logger.log('Telegram sent.'); return true; }
    else { Logger.log('Telegram error: ' + result.description); return false; }
  } catch (e) { Logger.log('Telegram failed: ' + e.toString()); return false; }
}

// ==================== TELEGRAM ALERTS ====================
function checkProximityAlert() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var data = pending.getDataRange().getValues();
  var alerts = [];

  for (var i = 1; i < data.length; i++) {
    if (data[i][PCOL.STATUS] === 'PENDING') {
      var ticker = data[i][PCOL.TICKER];
      var type = data[i][PCOL.TYPE];
      var target = parseFloat(data[i][PCOL.TARGET]);
      var current = parseFloat(data[i][PCOL.CURRENT]);

      if (!current || !target) continue;

      var proximity = Math.abs(current - target) / target * 100;
      if (proximity <= 2) {
        alerts.push('📊 ' + ticker + ' ' + type + ' @ ' + current.toLocaleString() +
          ' (Target: ' + target.toLocaleString() + ', Gap: ' + proximity.toFixed(2) + '%)');
      }
    }
  }

  if (alerts.length > 0) {
    var msg = '🔔 PROXIMITY ALERT!\n\n' + alerts.join('\n') +
      '\n⏰ ' + Utilities.formatDate(new Date(), CONFIG.MARKET.TIMEZONE, 'dd MMM yyyy HH:mm') + ' WIB';
    sendTelegram(msg);
  }
}

function sendDailySummary() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var settings = ss.getSheetByName(CONFIG.SHEETS.SETTINGS);
  var data = tradeLog.getDataRange().getValues();
  var modal = parseFloat(settings.getRange('B4').getValue()) || 100000000;

  var today = Utilities.formatDate(new Date(), CONFIG.MARKET.TIMEZONE, 'yyyy-MM-dd');
  var todayPnl = 0, todayTrades = 0, todayWins = 0;

  for (var i = 1; i < data.length; i++) {
    if (data[i][COL.STATUS] === 'CLOSED' && data[i][COL.EXIT_DATE]) {
      var exitDate = Utilities.formatDate(new Date(data[i][COL.EXIT_DATE]), CONFIG.MARKET.TIMEZONE, 'yyyy-MM-dd');
      if (exitDate === today) {
        todayTrades++;
        var pnl = parseFloat(data[i][COL.PNL_RP]);
        todayPnl += pnl;
        if (pnl >= 0) todayWins++;
      }
    }
  }

  var todayReturn = (todayPnl / modal) * 100;
  var winRate = todayTrades > 0 ? (todayWins / todayTrades * 100) : 0;

  var msg = '📊 DAILY SUMMARY\n\n' +
    '📅 ' + today + '\n' +
    '💰 P&L: Rp ' + todayPnl.toLocaleString() + ' (' + todayReturn.toFixed(2) + '%)\n' +
    '📈 Trades: ' + todayTrades + ' (Win: ' + todayWins + ', Rate: ' + winRate.toFixed(1) + '%)\n' +
    '⏰ ' + Utilities.formatDate(new Date(), CONFIG.MARKET.TIMEZONE, 'HH:mm') + ' WIB';

  sendTelegram(msg);
}

function checkDrawdownAlert() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var settings = ss.getSheetByName(CONFIG.SHEETS.SETTINGS);
  var data = tradeLog.getDataRange().getValues();
  var modal = parseFloat(settings.getRange('B4').getValue()) || 100000000;

  var equity = modal, peak = modal, maxDD = 0;
  var sortedTrades = data.slice(1).filter(function(r) { return r[COL.STATUS] === 'CLOSED'; })
    .sort(function(a, b) { return new Date(a[COL.EXIT_DATE]) - new Date(b[COL.EXIT_DATE]); });

  for (var j = 0; j < sortedTrades.length; j++) {
    equity += parseFloat(sortedTrades[j][COL.PNL_RP]);
    if (equity > peak) peak = equity;
    var dd = (peak - equity) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }

  if (maxDD > 10) {
    // Throttle: max 1 alert per session (check last sent time)
    var props = PropertiesService.getScriptProperties();
    var lastSent = props.getProperty('LAST_DRAWDOWN_ALERT');
    var now = new Date().getTime();
    if (lastSent && (now - parseInt(lastSent)) < 3600000) return; // 1 hour throttle

    var msg = '⚠️ DRAWDOWN ALERT!\n\n' +
      '📉 Max Drawdown: ' + maxDD.toFixed(2) + '%\n' +
      '💰 Current Equity: Rp ' + equity.toLocaleString() + '\n' +
      '⏰ ' + Utilities.formatDate(new Date(), CONFIG.MARKET.TIMEZONE, 'dd MMM yyyy HH:mm') + ' WIB';
    sendTelegram(msg);
    props.setProperty('LAST_DRAWDOWN_ALERT', String(now));
  }
}

function checkConsecutiveLossAlert() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var data = tradeLog.getDataRange().getValues();

  var sortedTrades = data.slice(1).filter(function(r) { return r[COL.STATUS] === 'CLOSED'; })
    .sort(function(a, b) { return new Date(a[COL.EXIT_DATE]) - new Date(b[COL.EXIT_DATE]); });

  var consecutiveLosses = 0;
  for (var i = sortedTrades.length - 1; i >= 0; i--) {
    if (parseFloat(sortedTrades[i][COL.PNL_RP]) < 0) {
      consecutiveLosses++;
    } else {
      break;
    }
  }

  if (consecutiveLosses >= 3) {
    // Throttle: max 1 alert per session (check last sent time)
    var props = PropertiesService.getScriptProperties();
    var lastSent = props.getProperty('LAST_CONSECUTIVE_LOSS_ALERT');
    var now = new Date().getTime();
    if (lastSent && (now - parseInt(lastSent)) < 3600000) return; // 1 hour throttle

    var msg = '⚠️ CONSECUTIVE LOSS ALERT!\n\n' +
      '📉 ' + consecutiveLosses + ' trades rugi berturut-turut\n' +
      '⏰ ' + Utilities.formatDate(new Date(), CONFIG.MARKET.TIMEZONE, 'dd MMM yyyy HH:mm') + ' WIB';
    sendTelegram(msg);
    props.setProperty('LAST_CONSECUTIVE_LOSS_ALERT', String(now));
  }
}

// ==================== POSITION SIZE CALCULATOR ====================
function calculatePositionSize() {
  var ui = SpreadsheetApp.getUi();
  var settings = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEETS.SETTINGS);
  var modal = parseFloat(settings.getRange('B4').getValue()) || 100000000;

  var riskPct = ui.prompt('Position Size Calculator', 'Risk per trade (%):', ui.ButtonSet.OK_CANCEL);
  if (riskPct.getSelectedButton() !== ui.Button.OK) return;
  var riskPctVal = parseFloat(riskPct.getResponseText()) / 100;

  var entryPrice = ui.prompt('Position Size Calculator', 'Entry Price:', ui.ButtonSet.OK_CANCEL);
  if (entryPrice.getSelectedButton() !== ui.Button.OK) return;
  var entryVal = parseFloat(entryPrice.getResponseText());

  var slPrice = ui.prompt('Position Size Calculator', 'Stop Loss Price:', ui.ButtonSet.OK_CANCEL);
  if (slPrice.getSelectedButton() !== ui.Button.OK) return;
  var slVal = parseFloat(slPrice.getResponseText());

  if (!riskPctVal || !entryVal || !slVal || entryVal <= slVal) {
    ui.alert('❌ Input tidak valid! Entry harus lebih tinggi dari SL.');
    return;
  }

  var riskAmount = modal * riskPctVal;
  var riskPerShare = entryVal - slVal;
  var lots = Math.floor(riskAmount / (riskPerShare * 100));

  ui.alert('📊 POSITION SIZE CALCULATOR\n\n' +
    '💰 Modal: Rp ' + modal.toLocaleString() + '\n' +
    '⚠️ Risk: ' + (riskPctVal * 100).toFixed(1) + '% = Rp ' + riskAmount.toLocaleString() + '\n' +
    '📈 Entry: Rp ' + entryVal.toLocaleString() + '\n' +
    '📉 SL: Rp ' + slVal.toLocaleString() + '\n' +
    '🎯 Risk/Share: Rp ' + riskPerShare.toLocaleString() + '\n\n' +
    '✅ Recommended Size: ' + lots + ' lots');
}

// ==================== TRADE JOURNAL ====================
function addTradeJournal() {
  var ui = SpreadsheetApp.getUi();
  var tradeLog = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var data = tradeLog.getDataRange().getValues();

  var openTrades = [];
  for (var i = 1; i < data.length; i++) {
    if (data[i][COL.STATUS] === 'OPEN' || data[i][COL.STATUS] === 'PARTIAL' || data[i][COL.STATUS] === 'CLOSED') {
      openTrades.push(data[i][COL.ID] + ' | ' + data[i][COL.TICKER]);
    }
  }

  if (openTrades.length === 0) { ui.alert('Tidak ada trade.'); return; }

  var tradeId = ui.prompt('Trade Journal', 'Pilih Trade ID:\n\n' + openTrades.join('\n'), ui.ButtonSet.OK_CANCEL);
  if (tradeId.getSelectedButton() !== ui.Button.OK) return;
  var tradeIdVal = tradeId.getResponseText().toUpperCase().trim();

  var notes = ui.prompt('Trade Journal', 'Catatan untuk ' + tradeIdVal + ':', ui.ButtonSet.OK_CANCEL);
  if (notes.getSelectedButton() !== ui.Button.OK) return;
  var notesVal = notes.getResponseText();

  for (var j = 1; j < data.length; j++) {
    if (data[j][COL.ID] === tradeIdVal) {
      var existingNotes = data[j][COL.NOTES] || '';
      var newNotes = existingNotes ? existingNotes + ' | ' + notesVal : notesVal;
      tradeLog.getRange(j + 1, COL.NOTES + 1).setValue(newNotes);
      ui.alert('✅ Journal ditambahkan ke ' + tradeIdVal);
      return;
    }
  }
  ui.alert('❌ Trade ID tidak ditemukan!');
}

// ==================== EXPORT TO CSV ====================
function exportToCSV() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var data = tradeLog.getDataRange().getValues();

  var csv = '';
  for (var i = 0; i < data.length; i++) {
    var row = [];
    for (var j = 0; j < data[i].length; j++) {
      row.push('"' + String(data[i][j]).replace(/"/g, '""') + '"');
    }
    csv += row.join(',') + '\n';
  }

  var blob = Utilities.newBlob(csv, 'text/csv', 'trade_log_' +
    Utilities.formatDate(new Date(), CONFIG.MARKET.TIMEZONE, 'yyyyMMdd_HHmmss') + '.csv');

  var folder = DriveApp.getRootFolder();
  var file = folder.createFile(blob);

  SpreadsheetApp.getUi().alert('✅ CSV exported!\n\nFile: ' + file.getName() +
    '\nURL: ' + file.getUrl());
}

// ==================== MULTI-TICKER WATCHLIST ====================
function showWatchlist() {
  var ui = SpreadsheetApp.getUi();
  var result = ui.prompt('Watchlist', 'Masukkan ticker (pisahkan koma):\nContoh: BBCA, BMRI, BBRI', ui.ButtonSet.OK_CANCEL);
  if (result.getSelectedButton() !== ui.Button.OK) return;

  var tickers = result.getResponseText().toUpperCase().split(',').map(function(t) { return t.trim(); });
  if (tickers.length === 0) { ui.alert('Tidak ada ticker.'); return; }

  var prices = getIDXPricesBatch(tickers);
  var msg = '📊 WATCHLIST\n\n';

  for (var i = 0; i < tickers.length; i++) {
    var priceData = prices[tickers[i]];
    if (priceData && priceData.price) {
      msg += tickers[i] + ': Rp ' + priceData.price.toLocaleString() +
        ' (' + priceData.changePct + '%)\n';
    } else {
      msg += tickers[i] + ': Error\n';
    }
  }

  msg += '\n⏰ ' + Utilities.formatDate(new Date(), CONFIG.MARKET.TIMEZONE, 'dd MMM yyyy HH:mm') + ' WIB';
  ui.alert(msg);
}

// ==================== AUTO-RESTART TRIGGER ====================
function ensureTriggerActive() {
  var triggers = ScriptApp.getProjectTriggers();
  var hasAutoCheck = false;

  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'autoCheck') {
      hasAutoCheck = true;
      break;
    }
  }

  if (!hasAutoCheck) {
    Logger.log('Auto-check trigger not found. Restarting...');
    createTrigger();
  }
}

// ==================== DASHBOARD ====================
function updateDashboard() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var dashboard = ss.getSheetByName(CONFIG.SHEETS.DASHBOARD);
  var settings = ss.getSheetByName(CONFIG.SHEETS.SETTINGS);
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var data = tradeLog.getDataRange().getValues();

  var totalTrades = 0, closedTrades = 0, winningTrades = 0, losingTrades = 0;
  var totalPnl = 0, grossProfit = 0, grossLoss = 0, returns = [];
  var monthlyPnl = {};

  for (var i = 1; i < data.length; i++) {
    var status = data[i][COL.STATUS];
    if (status === 'OPEN' || status === 'PARTIAL' || status === 'CLOSED') totalTrades++;
    if (status === 'CLOSED') {
      closedTrades++;
      var pnl = parseFloat(data[i][COL.PNL_RP]);
      var pnlPct = parseFloat(data[i][COL.PNL_PCT]);
      var exitDate = new Date(data[i][COL.EXIT_DATE]);
      var monthKey = Utilities.formatDate(exitDate, CONFIG.MARKET.TIMEZONE, 'yyyy-MM');
      totalPnl += pnl;
      returns.push(pnlPct);
      if (pnl >= 0) { winningTrades++; grossProfit += pnl; }
      else { losingTrades++; grossLoss += Math.abs(pnl); }
      if (!monthlyPnl[monthKey]) monthlyPnl[monthKey] = 0;
      monthlyPnl[monthKey] += pnl;
    }
  }

  var winRate = closedTrades > 0 ? (winningTrades / closedTrades * 100) : 0;
  var avgReturn = returns.length > 0 ? returns.reduce(function(a, b) { return a + b; }, 0) / returns.length : 0;
  var profitFactor = grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? Infinity : 0);
  var modal = parseFloat(settings.getRange('B4').getValue()) || 100000000;
  var totalReturn = (totalPnl / modal) * 100;

  var equity = modal, peak = modal, maxDD = 0;
  var sortedTrades = data.slice(1).filter(function(r) { return r[COL.STATUS] === 'CLOSED'; })
    .sort(function(a, b) { return new Date(a[COL.EXIT_DATE]) - new Date(b[COL.EXIT_DATE]); });
  for (var j = 0; j < sortedTrades.length; j++) {
    equity += parseFloat(sortedTrades[j][COL.PNL_RP]);
    if (equity > peak) peak = equity;
    var dd = (peak - equity) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }

  var avgReturnDecimal = avgReturn / 100;
  var variance = 0;
  for (var k = 0; k < returns.length; k++) variance += Math.pow(returns[k] / 100 - avgReturnDecimal, 2);
  var stdDev = returns.length > 1 ? Math.sqrt(variance / (returns.length - 1)) : 0;
  var sharpe = stdDev > 0 ? (avgReturnDecimal / stdDev) : 0;

  var downsideVariance = 0, downsideCount = 0;
  for (var l = 0; l < returns.length; l++) {
    if (returns[l] < 0) { downsideVariance += Math.pow(returns[l] / 100, 2); downsideCount++; }
  }
  var downsideDev = downsideCount > 1 ? Math.sqrt(downsideVariance / downsideCount) : 0;
  var sortino = downsideDev > 0 ? (avgReturnDecimal / downsideDev) : 0;
  var calmar = maxDD > 0 ? totalReturn / maxDD : 0;

  var pData = pending.getDataRange().getValues();
  var pendingCount = 0;
  for (var m = 1; m < pData.length; m++) { if (pData[m][PCOL.STATUS] === 'PENDING') pendingCount++; }

  // Calculate Unrealized P&L from open trades
  var unrealizedPnl = 0;
  var openTradeCount = 0;
  for (var n = 1; n < data.length; n++) {
    if (data[n][COL.STATUS] === 'OPEN' || data[n][COL.STATUS] === 'PARTIAL') {
      openTradeCount++;
      var ticker = data[n][COL.TICKER];
      var entryPrice = parseFloat(data[n][COL.ENTRY]);
      var remaining = parseInt(data[n][COL.REMAINING]);

      // Find current price from pending orders
      var currentPrice = 0;
      for (var p = 1; p < pData.length; p++) {
        if (pData[p][PCOL.TICKER] === ticker && pData[p][PCOL.STATUS] === 'PENDING') {
          currentPrice = parseFloat(pData[p][PCOL.CURRENT]) || 0;
          break;
        }
      }

      if (currentPrice > 0 && entryPrice > 0) {
        var unrealized = (currentPrice - entryPrice) * remaining * 100;
        var unrealizedFee = (currentPrice * remaining * 100) * CONFIG.FEE.SELL;
        unrealizedPnl += unrealized - unrealizedFee;
      }
    }
  }

  dashboard.clear();
  dashboard.getRange('A1').setValue('📊 PAPER TRADING DASHBOARD').setFontSize(16).setFontWeight('bold');
  dashboard.getRange('A2').setValue('Terakhir update:');
  dashboard.getRange('B2').setValue(new Date()).setNumberFormat('dd MMM yyyy HH:mm:ss');
  dashboard.getRange('D2').setValue('Last Price Update:');
  dashboard.getRange('E2').setValue(new Date()).setNumberFormat('dd MMM yyyy HH:mm:ss');

  dashboard.getRange('A4').setValue('💰 SUMMARY').setFontSize(12).setFontWeight('bold');
  dashboard.getRange('A5:B11').setValues([
    ['Modal', modal], ['Total P&L (Closed)', totalPnl], ['Unrealized P&L', unrealizedPnl],
    ['Total Return', totalReturn / 100], ['Total Trades', totalTrades],
    ['Closed Trades', closedTrades], ['Pending Orders', pendingCount]
  ]);
  dashboard.getRange('B5').setNumberFormat('#,##0');
  dashboard.getRange('B6').setNumberFormat('#,##0');
  dashboard.getRange('B7').setNumberFormat('#,##0');
  dashboard.getRange('B8').setNumberFormat('0.00%');
  dashboard.getRange('B7').setBackground(unrealizedPnl >= 0 ? '#E6F4EA' : '#FCE8E6');

  // Calculate Average Holding Time
  var totalHoldingHours = 0, holdingCount = 0;
  for (var h = 0; h < sortedTrades.length; h++) {
    if (sortedTrades[h][COL.DATE] && sortedTrades[h][COL.EXIT_DATE]) {
      var entryDate = new Date(sortedTrades[h][COL.DATE]);
      var exitDate = new Date(sortedTrades[h][COL.EXIT_DATE]);
      var holdingHours = (exitDate - entryDate) / (1000 * 60 * 60);
      totalHoldingHours += holdingHours;
      holdingCount++;
    }
  }
  var avgHoldingHours = holdingCount > 0 ? totalHoldingHours / holdingCount : 0;
  var avgHoldingDays = avgHoldingHours / 24;

  // Calculate Risk per Trade (average SL distance)
  var totalRisk = 0, riskCount = 0;
  for (var r = 1; r < pData.length; r++) {
    if (pData[r][PCOL.TYPE] === 'STOPLOSS' && pData[r][PCOL.STATUS] === 'MATCHED') {
      var slTarget = parseFloat(pData[r][PCOL.TARGET]);
      var slCurrent = parseFloat(pData[r][PCOL.CURRENT]) || 0;
      if (slTarget > 0 && slCurrent > 0) {
        totalRisk += Math.abs(slCurrent - slTarget) / slTarget * 100;
        riskCount++;
      }
    }
  }
  var avgRisk = riskCount > 0 ? totalRisk / riskCount : 0;

  dashboard.getRange('D4').setValue('📈 RISK METRICS').setFontSize(12).setFontWeight('bold');
  dashboard.getRange('D5:E14').setValues([
    ['Win Rate', winRate / 100], ['Profit Factor', profitFactor], ['Avg Return', avgReturn / 100],
    ['Max Drawdown', maxDD / 100], ['Sharpe Ratio', sharpe], ['Sortino Ratio', sortino],
    ['Calmar Ratio', calmar], ['Total Return', totalReturn / 100],
    ['Avg Holding Time', avgHoldingDays > 0 ? avgHoldingDays.toFixed(1) + ' days' : '-'],
    ['Avg Risk/Trade', avgRisk > 0 ? avgRisk.toFixed(2) + '%' : '-']
  ]);
  dashboard.getRange('E5').setNumberFormat('0.0%');
  dashboard.getRange('E6').setNumberFormat('0.00');
  dashboard.getRange('E7').setNumberFormat('0.00%');
  dashboard.getRange('E8').setNumberFormat('0.00%');
  dashboard.getRange('E9').setNumberFormat('0.00');
  dashboard.getRange('E10').setNumberFormat('0.00');
  dashboard.getRange('E11').setNumberFormat('0.00');
  dashboard.getRange('E12').setNumberFormat('0.00%');

  dashboard.getRange('E5').setBackground(winRate >= 50 ? '#E6F4EA' : '#FCE8E6');
  dashboard.getRange('E6').setBackground(profitFactor >= 2 ? '#E6F4EA' : '#FCE8E6');
  dashboard.getRange('E8').setBackground(maxDD <= 5 ? '#E6F4EA' : '#FCE8E6');

  var months = Object.keys(monthlyPnl).sort();
  if (months.length > 0) {
    dashboard.getRange('A13').setValue('📅 MONTHLY P&L').setFontSize(12).setFontWeight('bold');
    dashboard.getRange('A14').setValue('Month').setFontWeight('bold');
    dashboard.getRange('B14').setValue('P&L').setFontWeight('bold');
    dashboard.getRange('C14').setValue('Cumulative').setFontWeight('bold');
    var cumPnl = 0;
    for (var n = 0; n < months.length; n++) {
      cumPnl += monthlyPnl[months[n]];
      dashboard.getRange(15 + n, 1).setValue(months[n]);
      dashboard.getRange(15 + n, 2).setValue(monthlyPnl[months[n]]).setNumberFormat('#,##0');
      dashboard.getRange(15 + n, 3).setValue(cumPnl).setNumberFormat('#,##0');
      dashboard.getRange(15 + n, 2).setBackground(monthlyPnl[months[n]] >= 0 ? '#E6F4EA' : '#FCE8E6');
    }
  }

  dashboard.setColumnWidth(1, 160);
  dashboard.setColumnWidth(2, 150);
  dashboard.setColumnWidth(4, 160);
  dashboard.setColumnWidth(5, 150);
}

// ==================== EQUITY CURVE ====================
function generateEquityCurve() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var equitySheet = ss.getSheetByName(CONFIG.SHEETS.EQUITY);
  var settings = ss.getSheetByName(CONFIG.SHEETS.SETTINGS);

  if (!equitySheet) {
    equitySheet = ss.insertSheet(CONFIG.SHEETS.EQUITY);
    equitySheet.appendRow(['Date', 'Total Equity', 'Modal', 'Return (%)']);
    equitySheet.getRange('1:1').setFontWeight('bold').setBackground('#34A853').setFontColor('#FFFFFF');
    equitySheet.setFrozenRows(1);
  }

  var modal = parseFloat(settings.getRange('B4').getValue()) || 100000000;
  var data = tradeLog.getDataRange().getValues();
  var closedTrades = [];
  for (var i = 1; i < data.length; i++) {
    if (data[i][COL.STATUS] === 'CLOSED' && data[i][COL.EXIT_DATE]) {
      closedTrades.push({
        exitDate: new Date(data[i][COL.EXIT_DATE]),
        pnl: parseFloat(data[i][COL.PNL_RP])
      });
    }
  }
  closedTrades.sort(function(a, b) { return a.exitDate - b.exitDate; });

  var equity = modal;
  var equityData = [['Date', 'Total Equity', 'Modal', 'Return (%)']];
  equityData.push([new Date(), modal, modal, 0]);

  for (var j = 0; j < closedTrades.length; j++) {
    equity += closedTrades[j].pnl;
    equityData.push([closedTrades[j].exitDate, equity, modal, ((equity - modal) / modal) * 100]);
  }

  equitySheet.clearContents();
  equitySheet.getRange(1, 1, equityData.length, 4).setValues(equityData);
  equitySheet.getRange('1:1').setFontWeight('bold').setBackground('#34A853').setFontColor('#FFFFFF');
  equitySheet.setFrozenRows(1);
  equitySheet.setColumnWidth(1, 120);
  equitySheet.setColumnWidth(2, 130);
  equitySheet.setColumnWidth(3, 130);
  equitySheet.setColumnWidth(4, 100);

  var charts = equitySheet.getCharts();
  for (var k = 0; k < charts.length; k++) equitySheet.removeChart(charts[k]);

  if (equityData.length > 2) {
    var chart = equitySheet.newChart()
      .setChartType(Charts.ChartType.LINE)
      .addRange(equitySheet.getRange(1, 1, equityData.length, 1))
      .addRange(equitySheet.getRange(1, 2, equityData.length, 1))
      .setPosition(1, 6, 0, 0)
      .setOption('title', 'Equity Curve')
      .setOption('width', 800).setOption('height', 400)
      .setOption('hAxis', { title: 'Date' })
      .setOption('vAxis', { title: 'Equity (Rp)', format: '#,##0' })
      .setOption('colors', ['#34A853'])
      .setOption('lineWidth', 2)
      .setOption('legend', { position: 'none' })
      .build();
    equitySheet.insertChart(chart);
  }
}

// ==================== TRIGGER MANAGEMENT ====================
function createTrigger() {
  deleteTrigger();
  ScriptApp.newTrigger('autoCheck').timeBased().everyMinutes(CONFIG.TRIGGER.INTERVAL_MINUTES).create();
  SpreadsheetApp.getUi().alert('✅ Auto-monitor started!\n\nInterval: 1 menit\nActive: 09:00-16:01 WIB\n(skip lunch)\n\nStop: Paper Trading → Auto Monitor → Stop');
}

function deleteTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'autoCheck') ScriptApp.deleteTrigger(triggers[i]);
  }
}

function getTriggerStatus() {
  var triggers = ScriptApp.getProjectTriggers();
  var active = [];
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'autoCheck') {
      active.push({ interval: triggers[i].getMinutedInterval(), created: triggers[i].getCreatedAt() });
    }
  }
  var msg = '🤖 AUTO MONITOR STATUS\n\n';
  if (active.length > 0) {
    msg += 'Status: ✅ ACTIVE\nInterval: ' + active[0].interval + ' menit\nCreated: ' + active[0].created;
  } else {
    msg += 'Status: ❌ NOT ACTIVE\nKlik Start untuk mengaktifkan.';
  }
  SpreadsheetApp.getUi().alert(msg);
}

function autoCheck() {
  try {
    if (!isMarketOpen()) {
      Logger.log('Outside monitoring window.');
      return;
    }

    var now = new Date();
    var jakartaTime = Utilities.formatDate(now, CONFIG.MARKET.TIMEZONE, 'HH:mm');
    var jakartaDay = Utilities.formatDate(now, CONFIG.MARKET.TIMEZONE, 'EEEE');
    var h = parseInt(jakartaTime.split(':')[0]);
    var m = parseInt(jakartaTime.split(':')[1]);
    var t = h * 60 + m;
    var isFriday = (jakartaDay === 'Friday');

    var marketStart = 540;   // 09:00
    var marketEnd = isFriday ? CONFIG.MARKET.FRIDAY_SESSION1_END : CONFIG.MARKET.WEEKDAY_SESSION1_END;
    var marketStart2 = isFriday ? CONFIG.MARKET.FRIDAY_SESSION2_START : CONFIG.MARKET.WEEKDAY_SESSION2_START;
    var marketEnd2 = 961;    // 16:01

    var isMarketSession = false;
    if ((t >= marketStart && t <= marketEnd) || (t >= marketStart2 && t <= marketEnd2)) {
      isMarketSession = true;
    }

    var phase = isMarketSession ? 'MARKET' : (t < marketStart ? 'PRE-MARKET' : 'POST-MARKET');
    Logger.log('=== AUTO CHECK === ' + jakartaTime + ' WIB | Phase: ' + phase);

    if (isMarketSession) {
      refreshPrices();
      checkGapAndCancel();
      checkPendingOrders();
      checkProximityAlert();
      checkDrawdownAlert();
      checkConsecutiveLossAlert();
      updateDashboard();
    } else {
      refreshPrices();
      updateDashboard();
    }
  } catch (e) {
    Logger.log('AutoCheck error: ' + e.toString());
  }
}

// ==================== SIDEBAR FORMS ====================
function showOpenTradeForm() {
  var html = HtmlService.createHtmlOutput(
    '<h3>➕ Open Trade</h3><hr>' +
    '<b>Ticker:</b> <input type="text" id="ticker" placeholder="BBCA" style="width:100%;margin:5px 0;padding:8px;"><br>' +
    '<b>Qty (lot):</b> <input type="number" id="qty" placeholder="10" style="width:100%;margin:5px 0;padding:8px;"><br>' +
    '<b>Entry Price:</b> <input type="number" id="price" placeholder="9500" style="width:100%;margin:5px 0;padding:8px;"><br>' +
    '<button onclick="submit()" style="width:100%;padding:10px;background:#34A853;color:white;border:none;cursor:pointer;margin-top:10px;">Submit</button>' +
    '<script>function submit(){var t=document.getElementById("ticker").value.toUpperCase().trim();var q=parseInt(document.getElementById("qty").value);var p=parseFloat(document.getElementById("price").value);if(!t||!q||!p){alert("Semua field harus diisi!");return;}google.script.run.openTrade(t,q,p);alert("Trade opened!");google.script.host.close();}</script>'
  ).setWidth(300).setHeight(300);
  SpreadsheetApp.getUi().showSidebar(html);
}

function showCloseTradeForm() {
  var html = HtmlService.createHtmlOutput(
    '<h3>➖ Close Trade</h3><hr>' +
    '<b>Trade ID:</b> <input type="text" id="tradeId" placeholder="T001" style="width:100%;margin:5px 0;padding:8px;"><br>' +
    '<b>Exit Price:</b> <input type="number" id="exitPrice" placeholder="9800" style="width:100%;margin:5px 0;padding:8px;"><br>' +
    '<button onclick="submit()" style="width:100%;padding:10px;background:#EA4335;color:white;border:none;cursor:pointer;margin-top:10px;">Close Trade</button>' +
    '<script>function submit(){var id=document.getElementById("tradeId").value.toUpperCase().trim();var p=parseFloat(document.getElementById("exitPrice").value);if(!id||!p){alert("Semua field harus diisi!");return;}google.script.run.closeTradeById(id,p);alert("Trade closed!");google.script.host.close();}</script>'
  ).setWidth(300).setHeight(250);
  SpreadsheetApp.getUi().showSidebar(html);
}

function showPendingOrderForm() {
  var html = HtmlService.createHtmlOutput(
    '<h3>📋 Bracket Order</h3><hr>' +
    '<b>Ticker:</b> <input type="text" id="ticker" placeholder="BBCA" style="width:100%;margin:3px 0;padding:6px;"><br>' +
    '<b>Qty (lot):</b> <input type="number" id="qty" placeholder="10" style="width:100%;margin:3px 0;padding:6px;"><br>' +
    '<b>Entry Price:</b> <input type="number" id="entry" placeholder="9500" style="width:100%;margin:3px 0;padding:6px;"><br>' +
    '<hr><b>Take Profit:</b><br>' +
    'TP1: <input type="number" id="tp1" placeholder="10000" style="width:45%;padding:4px;"> <input type="number" id="tp1pct" placeholder="50" style="width:20%;padding:4px;">%<br>' +
    'TP2: <input type="number" id="tp2" placeholder="10500" style="width:45%;padding:4px;"> <input type="number" id="tp2pct" placeholder="30" style="width:20%;padding:4px;">%<br>' +
    'TP3: <input type="number" id="tp3" placeholder="11000" style="width:45%;padding:4px;"> <input type="text" id="tp3pct" placeholder="%" style="width:20%;padding:4px;background:#f0f0f0;" disabled>%<br>' +
    '<b>Stop Loss:</b> <input type="number" id="sl" placeholder="9000" style="width:100%;margin:3px 0;padding:6px;"><br>' +
    '<button onclick="submit()" style="width:100%;padding:10px;background:#FBBC04;color:black;border:none;cursor:pointer;margin-top:10px;">Add Order</button>' +
    '<script>function submit(){var t=document.getElementById("ticker").value.toUpperCase().trim();var q=parseInt(document.getElementById("qty").value);var e=parseFloat(document.getElementById("entry").value);var t1=parseFloat(document.getElementById("tp1").value);var t1p=parseInt(document.getElementById("tp1pct").value);var t2=parseFloat(document.getElementById("tp2").value);var t2p=parseInt(document.getElementById("tp2pct").value);var t3=parseFloat(document.getElementById("tp3").value);var sl=parseFloat(document.getElementById("sl").value);if(!t||!q||!e||!t1||!t2||!t3||!sl){alert("Semua field harus diisi!");return;}google.script.run.webAddPending(t,q,e,t1,t1p,t2,t2p,t3,sl);alert("Bracket order added!");google.script.host.close();}</script>'
  ).setWidth(300).setHeight(500);
  SpreadsheetApp.getUi().showSidebar(html);
}

function showSettings() {
  SpreadsheetApp.getUi().alert('⚙️ SETTINGS\n\nBuka sheet "Settings" untuk mengubah:\n• Modal Awal\n• Buy/Sell Fee\n• Telegram Bot Token\n• Telegram Chat ID');
}

// ==================== WEB APP HELPER FUNCTIONS ====================
function openTrade(ticker, qty, price) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var tradeId = generateTradeId();
  var entryTotal = price * qty * 100;
  var entryFee = entryTotal * CONFIG.FEE.BUY;
  var now = new Date();

  tradeLog.appendRow([
    tradeId, now, ticker, qty, price, entryFee, entryTotal + entryFee,
    '', '', '', '', '', '', 'OPEN', qty, '', 'Web App'
  ]);
  var row = tradeLog.getLastRow();
  tradeLog.getRange(row, 1, 1, tradeLog.getLastColumn()).setBackground('#E6F4EA');
  tradeLog.getRange(row, COL.STATUS + 1).setFontWeight('bold');
  return tradeId;
}

function closeTradeById(tradeId, exitPrice) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var data = tradeLog.getDataRange().getValues();

  for (var i = 1; i < data.length; i++) {
    if (data[i][COL.ID] === tradeId && (data[i][COL.STATUS] === 'OPEN' || data[i][COL.STATUS] === 'PARTIAL')) {
      var row = i + 1;
      var qty = parseInt(data[i][COL.REMAINING]);
      var originalQty = parseInt(data[i][COL.QTY]);
      var entryTotal = parseFloat(data[i][COL.ENTRY_TOTAL]);
      var now = new Date();

      var exitTotal = exitPrice * qty * 100;
      var exitFee = exitTotal * CONFIG.FEE.SELL;
      var pnl = (exitTotal - exitFee) - (entryTotal * qty / originalQty);
      var pnlPct = (exitPrice - parseFloat(data[i][COL.ENTRY])) / parseFloat(data[i][COL.ENTRY]) * 100;

      tradeLog.getRange(row, COL.EXIT_DATE + 1).setValue(now);
      tradeLog.getRange(row, COL.EXIT_PRICE + 1).setValue(exitPrice);
      tradeLog.getRange(row, COL.EXIT_FEE + 1).setValue(exitFee);
      tradeLog.getRange(row, COL.EXIT_TOTAL + 1).setValue(exitTotal - exitFee);
      tradeLog.getRange(row, COL.PNL_RP + 1).setValue(pnl);
      tradeLog.getRange(row, COL.PNL_PCT + 1).setValue(pnlPct);
      tradeLog.getRange(row, COL.STATUS + 1).setValue('CLOSED').setFontWeight('bold');
      tradeLog.getRange(row, COL.REMAINING + 1).setValue(0);

      tradeLog.getRange(row, COL.PNL_RP + 1).setBackground(pnl >= 0 ? '#E6F4EA' : '#FCE8E6');
      tradeLog.getRange(row, COL.PNL_PCT + 1).setBackground(pnl >= 0 ? '#E6F4EA' : '#FCE8E6');

      var notes = data[i][COL.NOTES] || '';
      var match = notes.match(/Auto-matched from (P[A-Z0-9_]+)/);
      if (match) cancelPendingByParent(match[1]);
      else {
        // Find parent ID from Pending Orders for this ticker
        var parentId = findParentIdForTicker(data[i][COL.TICKER]);
        if (parentId) cancelPendingByParent(parentId);
      }

      return 'Closed: P&L Rp ' + pnl.toLocaleString();
    }
  }
  return 'Trade not found or already closed.';
}

function webAddPending(ticker, qty, entry, tp1, tp1pct, tp2, tp2pct, tp3, sl) {
  ticker = ticker.toUpperCase().trim();
  var tp3pct = 100 - tp1pct - tp2pct;
  if (!ticker || !qty || !entry || !tp1 || !tp2 || !tp3 || !sl) {
    return { success: false, message: 'Semua field harus diisi!' };
  }
  if (tp1pct + tp2pct + tp3pct !== 100) {
    return { success: false, message: 'Total TP % harus 100%!' };
  }
  if (tp3pct <= 0) {
    return { success: false, message: 'TP3 % harus lebih dari 0%! Kurangi TP1 atau TP2 %.' };
  }
  if (entry >= tp1 || tp1 >= tp2 || tp2 >= tp3) {
    return { success: false, message: 'Harga TP harus berurutan: Entry < TP1 < TP2 < TP3!' };
  }
  if (sl >= entry) {
    return { success: false, message: 'Stop Loss harus lebih rendah dari Entry Price!' };
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var orderId = generateOrderId();
  var now = new Date();
  var livePrice = getIDXPrice(ticker);
  var currentPrice = livePrice.price || 0;

  pending.appendRow([
    orderId, now, ticker, 'BUY', qty, entry, currentPrice,
    currentPrice ? ((currentPrice - entry) / entry * 100).toFixed(2) : '0.00',
    'PENDING', '', '', 'Web App'
  ]);
  pending.getRange(pending.getLastRow(), 1, 1, pending.getLastColumn()).setBackground('#E6F4EA');

  var tp1Qty = Math.round(qty * tp1pct / 100);
  var tp2Qty = Math.round(qty * tp2pct / 100);
  var tp3Qty = qty - tp1Qty - tp2Qty;

  var items = [
    ['SELL', tp1Qty, tp1, tp1pct + '%', '#FCE8E6'],
    ['SELL', tp2Qty, tp2, tp2pct + '%', '#FCE8E6'],
    ['SELL', tp3Qty, tp3, tp3pct + '%', '#FCE8E6'],
    ['STOPLOSS', qty, sl, '100%', '#FDD663']
  ];

  for (var i = 0; i < items.length; i++) {
    var id = generateOrderId();
    pending.appendRow([
      id, now, ticker, items[i][0], items[i][1], items[i][2], currentPrice,
      currentPrice ? ((currentPrice - items[i][2]) / items[i][2] * 100).toFixed(2) : '0.00',
      'PENDING', orderId, items[i][3], 'Web App'
    ]);
    pending.getRange(pending.getLastRow(), 1, 1, pending.getLastColumn()).setBackground(items[i][4]);
  }

  return {
    success: true,
    message: 'Bracket order: ' + orderId + ' | ' + ticker + ' ' + qty + ' lots @ Rp ' + entry.toLocaleString()
  };
}

function webRefreshPrices() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var tickers = new Set();

  var pData = pending.getDataRange().getValues();
  for (var i = 1; i < pData.length; i++) {
    if (pData[i][PCOL.TICKER]) tickers.add(pData[i][PCOL.TICKER]);
  }
  var tData = tradeLog.getDataRange().getValues();
  for (var j = 1; j < tData.length; j++) {
    if (tData[j][COL.STATUS] === 'OPEN' || tData[j][COL.STATUS] === 'PARTIAL') tickers.add(tData[j][COL.TICKER]);
  }

  if (tickers.size === 0) return { success: true, message: 'Tidak ada ticker.' };

  var prices = getIDXPricesBatch(Array.from(tickers));
  var updated = 0;
  for (var k = 1; k < pData.length; k++) {
    if (pData[k][PCOL.TICKER]) {
      var priceData = prices[pData[k][PCOL.TICKER]];
      if (priceData && priceData.price) {
        var target = parseFloat(pData[k][PCOL.TARGET]);
        var current = priceData.price;
        pending.getRange(k + 1, PCOL.CURRENT + 1).setValue(current);
        pending.getRange(k + 1, PCOL.CHANGE + 1).setValue(((current - target) / target * 100).toFixed(2));
        updated++;
      }
    }
  }
  return { success: true, message: 'Refreshed ' + updated + ' tickers.' };
}

// ==================== WEB: WATCHLIST PRICES ====================
function webGetWatchlistPrices(tickers) {
  return getIDXPricesBatch(tickers);
}

// ==================== WEB: CANCEL PENDING ====================
function webCancelPending(orderId) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
    if (!pending) return { success: false, message: 'Sheet Pending Orders tidak ditemukan!' };

    var data = pending.getDataRange().getValues();
    var found = false;
    var parentId = null;

    // Find the order and determine parent ID
    for (var i = 1; i < data.length; i++) {
      if (data[i][PCOL.ID] === orderId && data[i][PCOL.STATUS] === 'PENDING') {
        found = true;
        // If this is a child order, get parent ID; if parent, use own ID
        parentId = data[i][PCOL.PARENT] || data[i][PCOL.ID];
        break;
      }
    }

    if (!found) {
      return { success: false, message: 'Order tidak ditemukan atau sudah diproses!' };
    }

    // Cancel entire bracket (parent + all children)
    cancelPendingByParent(parentId);

    var msg = '❌ BRACKET ORDER CANCELLED\n\n📋 Parent ID: ' + parentId;
    sendTelegram(msg);

    return { success: true, message: 'Bracket order ' + parentId + ' berhasil dibatalkan!' };
  } catch (e) {
    return { success: false, message: 'Error: ' + e.toString() };
  }
}

// ==================== WEB APP DATA FUNCTIONS ====================
function getDashboardData() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var settings = ss.getSheetByName(CONFIG.SHEETS.SETTINGS);
  var data = tradeLog.getDataRange().getValues();

  var totalTrades = 0, closedTrades = 0, winningTrades = 0, totalPnl = 0;
  var grossProfit = 0, grossLoss = 0, returns = [], monthlyPnl = {};

  for (var i = 1; i < data.length; i++) {
    var status = data[i][COL.STATUS];
    if (status === 'OPEN' || status === 'PARTIAL' || status === 'CLOSED') totalTrades++;
    if (status === 'CLOSED') {
      closedTrades++;
      var pnl = parseFloat(data[i][COL.PNL_RP]);
      var pnlPct = parseFloat(data[i][COL.PNL_PCT]);
      var exitDate = new Date(data[i][COL.EXIT_DATE]);
      var monthKey = Utilities.formatDate(exitDate, CONFIG.MARKET.TIMEZONE, 'yyyy-MM');
      totalPnl += pnl; returns.push(pnlPct);
      if (pnl >= 0) { winningTrades++; grossProfit += pnl; } else { grossLoss += Math.abs(pnl); }
      if (!monthlyPnl[monthKey]) monthlyPnl[monthKey] = 0;
      monthlyPnl[monthKey] += pnl;
    }
  }

  var winRate = closedTrades > 0 ? (winningTrades / closedTrades * 100) : 0;
  var avgReturn = returns.length > 0 ? returns.reduce(function(a, b) { return a + b; }, 0) / returns.length : 0;
  var profitFactor = grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? Infinity : 0);
  var modal = parseFloat(settings.getRange('B4').getValue()) || 100000000;
  var totalReturn = (totalPnl / modal) * 100;

  var equity = modal, peak = modal, maxDD = 0;
  var sortedTrades = data.slice(1).filter(function(r) { return r[COL.STATUS] === 'CLOSED'; })
    .sort(function(a, b) { return new Date(a[COL.EXIT_DATE]) - new Date(b[COL.EXIT_DATE]); });
  for (var j = 0; j < sortedTrades.length; j++) {
    equity += parseFloat(sortedTrades[j][COL.PNL_RP]);
    if (equity > peak) peak = equity;
    var dd = (peak - equity) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }

  var avgRDec = avgReturn / 100;
  var variance = 0;
  for (var k = 0; k < returns.length; k++) variance += Math.pow(returns[k] / 100 - avgRDec, 2);
  var stdDev = returns.length > 1 ? Math.sqrt(variance / (returns.length - 1)) : 0;
  var sharpe = stdDev > 0 ? (avgRDec / stdDev) : 0;
  var downVar = 0, downCnt = 0;
  for (var l = 0; l < returns.length; l++) { if (returns[l] < 0) { downVar += Math.pow(returns[l] / 100, 2); downCnt++; } }
  var downDev = downCnt > 1 ? Math.sqrt(downVar / downCnt) : 0;
  var sortino = downDev > 0 ? (avgRDec / downDev) : 0;
  var calmar = maxDD > 0 ? totalReturn / maxDD : 0;

  var pData = pending.getDataRange().getValues();
  var pendingCount = 0;
  for (var m = 1; m < pData.length; m++) { if (pData[m][PCOL.STATUS] === 'PENDING') pendingCount++; }

  var months = Object.keys(monthlyPnl).sort();
  var monthlyData = [], cumPnl = 0;
  for (var n = 0; n < months.length; n++) {
    cumPnl += monthlyPnl[months[n]];
    monthlyData.push({ month: months[n], pnl: monthlyPnl[months[n]], cumulative: cumPnl });
  }

  return {
    modal: modal, totalPnl: totalPnl, totalReturn: totalReturn,
    totalTrades: totalTrades, closedTrades: closedTrades, pendingCount: pendingCount,
    winRate: winRate, profitFactor: profitFactor, avgReturn: avgReturn,
    maxDD: maxDD, sharpe: sharpe, sortino: sortino, calmar: calmar,
    grossProfit: grossProfit, grossLoss: grossLoss,
    monthly: monthlyData,
    spreadsheetUrl: ss.getUrl(),
    timestamp: Utilities.formatDate(new Date(), CONFIG.MARKET.TIMEZONE, 'dd MMM yyyy HH:mm:ss') + ' WIB'
  };
}

function getOpenTrades() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var data = tradeLog.getDataRange().getValues();
  var trades = [];
  for (var i = 1; i < data.length; i++) {
    if (data[i][COL.STATUS] === 'OPEN' || data[i][COL.STATUS] === 'PARTIAL') {
      trades.push({
        id: data[i][COL.ID], date: Utilities.formatDate(new Date(data[i][COL.DATE]), 'Asia/Jakarta', 'dd MMM yyyy'),
        ticker: data[i][COL.TICKER], qty: data[i][COL.QTY], remaining: data[i][COL.REMAINING],
        entryPrice: data[i][COL.ENTRY], entryTotal: data[i][COL.ENTRY_TOTAL], status: data[i][COL.STATUS]
      });
    }
  }
  return trades;
}

function getClosedTrades() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tradeLog = ss.getSheetByName(CONFIG.SHEETS.TRADE_LOG);
  var data = tradeLog.getDataRange().getValues();
  var trades = [];
  for (var i = 1; i < data.length; i++) {
    if (data[i][COL.STATUS] === 'CLOSED') {
      trades.push({
        id: data[i][COL.ID], ticker: data[i][COL.TICKER], qty: data[i][COL.QTY],
        entryPrice: data[i][COL.ENTRY], exitPrice: data[i][COL.EXIT_PRICE],
        pnl: data[i][COL.PNL_RP], pnlPct: data[i][COL.PNL_PCT],
        exitDate: data[i][COL.EXIT_DATE] ? Utilities.formatDate(new Date(data[i][COL.EXIT_DATE]), 'Asia/Jakarta', 'dd MMM yyyy') : '-'
      });
    }
  }
  return trades;
}

function getPendingOrders() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pending = ss.getSheetByName(CONFIG.SHEETS.PENDING);
  var data = pending.getDataRange().getValues();
  var orders = [];
  for (var i = 1; i < data.length; i++) {
    if (data[i][PCOL.STATUS] === 'PENDING' || data[i][PCOL.STATUS] === 'MATCHED') {
      orders.push({
        id: data[i][PCOL.ID], date: Utilities.formatDate(new Date(data[i][PCOL.DATE]), 'Asia/Jakarta', 'dd MMM yyyy'),
        ticker: data[i][PCOL.TICKER], type: data[i][PCOL.TYPE], qty: data[i][PCOL.QTY],
        targetPrice: data[i][PCOL.TARGET], currentPrice: data[i][PCOL.CURRENT],
        changePct: data[i][PCOL.CHANGE], status: data[i][PCOL.STATUS], parentId: data[i][PCOL.PARENT]
      });
    }
  }
  return orders;
}

// ==================== WEB APP ENTRY POINT ====================
function doGet(e) {
  var template = HtmlService.createTemplateFromFile('WebApp');
  return template.evaluate()
    .setTitle('📊 Paper Trading IDX')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
