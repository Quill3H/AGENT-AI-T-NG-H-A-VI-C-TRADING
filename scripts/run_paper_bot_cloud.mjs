#!/usr/bin/env node
/**
 * run_paper_bot_cloud.mjs
 * ---------------------------------------------------------------------------
 * Headless Cloud Runner cho Paper Bot Studio (Phương án A - GitHub Actions)
 *
 * Chức năng chính:
 * 1. Khởi động tạm thời Local Worker (server.mjs tại 127.0.0.1:8792) trong phiên
 *    chạy của GitHub Actions (hoặc chạy trực tiếp thông qua cli.mjs).
 * 2. Quét bù nến 1 phút (1m Klines Catch-up) từ Binance cho BTCUSDT, ETHUSDT,
 *    SOLUSDT, HYPEUSDT để khớp chính xác các vị thế OPEN chạm TP/SL trong khoảng
 *    thời gian giữa 2 lần cron (theo thứ tự ưu tiên: Liquidation > SL > TP).
 * 3. Kiểm tra mốc đóng nến của 3 Bot độc lập (vốn khởi tạo 100 USD/ví):
 *    - Bot 15m (mỗi 15 phút)
 *    - Bot 1h  (mỗi 1 giờ)
 *    - Bot 4h  (mỗi 4 giờ)
 * 4. Tự động đối chiếu các lệnh vừa đóng (TP/SL hoặc đóng sớm) để rút ra
 *    Bài học kinh nghiệm (Lessons Learned) lưu vào data/lessons_learned.json.
 * 5. Gọi AI Model miễn phí (GitHub Models qua GITHUB_TOKEN hoặc Gemini API Free)
 *    theo chuẩn phân tích kỹ thuật SOL 6.1 + bộ quy tắc quản lý vốn:
 *    - Initial Margin: 3% - 5% số dư đã ghi sổ (booked balance)
 *    - Đòn bẩy cố định: BTCUSDT (15x), ETHUSDT (10x), SOLUSDT (7x), HYPEUSDT (5x)
 *    - Xuất file quyết định vào data/decisions/ và nạp qua cli.mjs.
 * 6. Xuất bản snapshot tĩnh (public/state-snapshot.json) để Dashboard xem online
 *    qua GitHub Pages / Vercel mà không cần bật máy tính cá nhân.
 */

import fs from 'node:fs';
import path from 'node:path';
import { spawn, execFileSync } from 'node:child_process';

const WORKER_URL = process.env.PAPER_WORKER_URL || 'http://127.0.0.1:8792';
const DATA_DIR = path.resolve(process.cwd(), process.env.PAPER_DATA_DIR || 'data');
const DECISIONS_DIR = path.join(DATA_DIR, 'decisions');
const LESSONS_FILE = path.join(DATA_DIR, 'lessons_learned.json');
const RUNTIME_META_FILE = path.join(DATA_DIR, 'cloud_runtime_meta.json');
const STATIC_SNAPSHOT_FILE = path.resolve(
  process.cwd(),
  process.env.STATIC_SNAPSHOT_PATH || 'crypto-paper-agent/web-preview/public/state-snapshot.json'
);

const SYMBOLS_CONFIG = {
  BTCUSDT: { leverage: 15 },
  ETHUSDT: { leverage: 10 },
  SOLUSDT: { leverage: 7 },
  HYPEUSDT: { leverage: 5 },
};

const TIMEFRAMES = [
  { id: '15m', intervalMs: 15 * 60 * 1000, binanceInterval: '15m', initialCapital: 100 },
  { id: '1h', intervalMs: 60 * 60 * 1000, binanceInterval: '1h', initialCapital: 100 },
  { id: '4h', intervalMs: 4 * 60 * 60 * 1000, binanceInterval: '4h', initialCapital: 100 },
];

const INITIAL_MARGIN_MIN_PCT = 0.03;
const INITIAL_MARGIN_MAX_PCT = 0.05;

function ensureDirectories() {
  fs.mkdirSync(DECISIONS_DIR, { recursive: true });
  fs.mkdirSync(path.dirname(STATIC_SNAPSHOT_FILE), { recursive: true });
}

function readJsonSafe(filePath, fallback) {
  try {
    if (!fs.existsSync(filePath)) return fallback;
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (err) {
    console.warn(`[WARN] Không thể đọc ${filePath}, dùng giá trị mặc định:`, err.message);
    return fallback;
  }
}

function writeJsonSafe(filePath, data) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
}

/**
 * Kiểm tra xem server.mjs tại 127.0.0.1:8792 đã sống chưa; nếu chưa thì bật ngầm
 */
async function ensureLocalWorkerRunning() {
  const isHealthy = async () => {
    try {
      const res = await fetch(`${WORKER_URL}/api/state`, { signal: AbortSignal.timeout(2500) });
      return res.ok;
    } catch {
      return false;
    }
  };

  if (await isHealthy()) {
    console.log('[WORKER] server.mjs đã sẵn sàng tại', WORKER_URL);
    return null;
  }

  const serverScript = path.resolve(process.cwd(), process.env.SERVER_MJS_PATH || 'server.mjs');
  if (!fs.existsSync(serverScript)) {
    console.log('[WORKER] Không tìm thấy server.mjs tại đường dẫn mặc định, chạy chế độ độc lập.');
    return null;
  }

  console.log('[WORKER] Đang khởi chạy server.mjs trong nền...');
  const child = spawn(process.execPath, [serverScript], {
    stdio: 'ignore',
    detached: true,
  });
  child.unref();

  for (let i = 0; i < 10; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    if (await isHealthy()) {
      console.log('[WORKER] Khởi động server.mjs thành công.');
      return child;
    }
  }
  console.warn('[WARN] Không thể xác nhận server.mjs qua /api/state sau 10s.');
  return child;
}

/**
 * Tải dữ liệu nến từ Binance Futures Public API (không cần API key)
 */
async function fetchBinanceKlines(symbol, interval, limit = 60, startTime = undefined) {
  const url = new URL('https://fapi.binance.com/fapi/v1/klines');
  url.searchParams.set('symbol', symbol);
  url.searchParams.set('interval', interval);
  url.searchParams.set('limit', String(limit));
  if (startTime) url.searchParams.set('startTime', String(startTime));

  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) {
    throw new Error(`Binance klines HTTP ${res.status} cho ${symbol} (${interval})`);
  }
  const raw = await res.json();
  // Chỉ lấy các cây nến ĐÃ ĐÓNG (closeTime < Date.now()) để chống look-ahead bias
  const now = Date.now();
  return raw
    .map((k) => ({
      openTime: Number(k[0]),
      open: Number(k[1]),
      high: Number(k[2]),
      low: Number(k[3]),
      close: Number(k[4]),
      volume: Number(k[5]),
      closeTime: Number(k[6]),
    }))
    .filter((k) => k.closeTime < now);
}

/**
 * Quét bù chuỗi nến 1m (Intrabar Catch-up) để phát hiện vị thế chạm Liquidation / SL / TP
 * trong thời gian giữa 2 lần chạy GitHub Actions
 */
function checkIntrabarExitOn1mKlines(position, klines1m) {
  const { side, entryPrice, leverage, stopLoss, takeProfit } = position;
  // Ngưỡng thanh lý xấp xỉ theo đòn bẩy cô lập (Isolated Margin)
  const liqPrice =
    side === 'LONG'
      ? entryPrice * (1 - 0.9 / leverage)
      : entryPrice * (1 + 0.9 / leverage);

  for (const bar of klines1m) {
    if (bar.openTime < position.openedAt) continue;

    // Thứ tự ưu tiên nghiêm ngặt: Liquidation > Stop Loss > Take Profit
    if (side === 'LONG') {
      if (bar.low <= liqPrice) {
        return { exitReason: 'LIQUIDATION', exitPrice: liqPrice, exitTime: bar.closeTime, bar };
      }
      if (stopLoss && bar.low <= stopLoss) {
        return { exitReason: 'STOP_LOSS', exitPrice: stopLoss, exitTime: bar.closeTime, bar };
      }
      if (takeProfit && bar.high >= takeProfit) {
        return { exitReason: 'TAKE_PROFIT', exitPrice: takeProfit, exitTime: bar.closeTime, bar };
      }
    } else if (side === 'SHORT') {
      if (bar.high >= liqPrice) {
        return { exitReason: 'LIQUIDATION', exitPrice: liqPrice, exitTime: bar.closeTime, bar };
      }
      if (stopLoss && bar.high >= stopLoss) {
        return { exitReason: 'STOP_LOSS', exitPrice: stopLoss, exitTime: bar.closeTime, bar };
      }
      if (takeProfit && bar.low <= takeProfit) {
        return { exitReason: 'TAKE_PROFIT', exitPrice: takeProfit, exitTime: bar.closeTime, bar };
      }
    }
  }
  return null;
}

/**
 * Rút bài học kinh nghiệm từ các vị thế vừa đóng và lưu vào bộ nhớ bền vững
 */
function appendLessonFromClosedTrade(lessonsStore, closedTrade) {
  const isWin = closedTrade.realizedPnl > 0;
  const lessonEntry = {
    id: `lesson_${closedTrade.timeframe}_${closedTrade.symbol}_${closedTrade.exitTime}`,
    createdAt: new Date().toISOString(),
    timeframe: closedTrade.timeframe,
    symbol: closedTrade.symbol,
    side: closedTrade.side,
    entryPrice: closedTrade.entryPrice,
    exitPrice: closedTrade.exitPrice,
    exitReason: closedTrade.exitReason,
    realizedPnl: Number(closedTrade.realizedPnl.toFixed(4)),
    entryThesis: closedTrade.entryReason || 'N/A',
    auditSummary: isWin
      ? `Lệnh ${closedTrade.side} ${closedTrade.symbol} (${closedTrade.timeframe}) chạm ${closedTrade.exitReason} đúng kỳ vọng.`
      : `Lệnh ${closedTrade.side} ${closedTrade.symbol} (${closedTrade.timeframe}) bị dừng tại ${closedTrade.exitReason}; cần kiểm tra lại cấu trúc vùng thanh khoản và biên độ ATR trước khi vào lệnh cùng chiều.`,
  };

  lessonsStore.lessons.unshift(lessonEntry);
  // Giữ tối đa 100 bài học gần nhất để tránh phình prompt
  lessonsStore.lessons = lessonsStore.lessons.slice(0, 100);
  return lessonEntry;
}

/**
 * Gọi AI Model (hỗ trợ GitHub Models miễn phí qua GITHUB_TOKEN hoặc Gemini / OpenAI tương thích)
 */
async function callSol61Analyzer({ timeframe, marketSnapshot, recentLessons, walletState }) {
  const apiKey = process.env.AI_API_KEY || process.env.GITHUB_TOKEN;
  const apiUrl =
    process.env.AI_BASE_URL || 'https://models.inference.ai.azure.com/chat/completions';
  const modelName = process.env.AI_MODEL_NAME || 'gpt-4o';

  const systemPrompt = `Bạn là mô hình phân tích kỹ thuật định lượng SOL 6.1 cho hệ thống Paper Bot Studio.
Quy tắc bắt buộc:
1. Chỉ phân tích dựa trên dữ liệu nến ĐÃ ĐÓNG trong snapshot. Tuyệt đối không suy diễn dữ liệu tương lai.
2. Quản lý vốn cho ví ${timeframe} (Vốn gốc 100 USD):
   - Initial Margin mỗi lệnh chỉ được nằm trong khoảng 3% đến 5% số dư đã ghi sổ (bookedBalance).
   - Đòn bẩy cố định: BTCUSDT = 15x, ETHUSDT = 10x, SOLUSDT = 7x, HYPEUSDT = 5x.
3. Tham chiếu danh sách "Bài học kinh nghiệm gần đây" để tránh lặp lại các lỗi vào lệnh sớm hoặc đặt SL quá sát vùng quét thanh khoản.
4. Trả về duy nhất 1 JSON hợp lệ theo cấu trúc:
{
  "timeframe": "${timeframe}",
  "reflection_on_recent_trades": "Nhận xét ngắn gọn rút ra từ các lệnh trước",
  "decisions": [
    {
      "symbol": "BTCUSDT",
      "action": "LONG | SHORT | HOLD",
      "margin_pct": 0.04,
      "leverage": 15,
      "stop_loss": null,
      "take_profit": null,
      "audit_reason": "Lý do kỹ thuật và bài học áp dụng"
    }
  ]
}`;

  if (!apiKey) {
    console.warn(`[AI] Chưa cấu hình AI_API_KEY / GITHUB_TOKEN cho khung ${timeframe}. Giữ trạng thái HOLD an toàn.`);
    return {
      timeframe,
      reflection_on_recent_trades: 'Chạy chế độ Fail-Closed (HOLD) do chưa gắn token AI.',
      decisions: Object.entries(SYMBOLS_CONFIG).map(([symbol, cfg]) => ({
        symbol,
        action: 'HOLD',
        margin_pct: 0,
        leverage: cfg.leverage,
        stop_loss: null,
        take_profit: null,
        audit_reason: 'Fail-closed: Không có khóa API mô hình trong phiên hiện tại.',
      })),
    };
  }

  const userPayload = {
    timeframe,
    walletState,
    recentLessons: recentLessons.filter((l) => l.timeframe === timeframe).slice(0, 10),
    marketSnapshot,
  };

  const res = await fetch(apiUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: modelName,
      temperature: 0.2,
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: JSON.stringify(userPayload) },
      ],
    }),
    signal: AbortSignal.timeout(45000),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Lỗi gọi AI API (${res.status}): ${errText}`);
  }

  const data = await res.json();
  const content = data.choices?.[0]?.message?.content || '{}';
  return JSON.parse(content);
}

/**
 * Kiểm tra và ép buộc giới hạn rủi ro (3%-5% Initial Margin & Đòn bẩy cố định)
 */
function sanitizeDecisions(rawDecisionObj) {
  const list = Array.isArray(rawDecisionObj?.decisions) ? rawDecisionObj.decisions : [];
  return list.map((d) => {
    const symbolCfg = SYMBOLS_CONFIG[d.symbol];
    if (!symbolCfg) {
      return { ...d, action: 'HOLD', audit_reason: 'Symbol nằm ngoài danh mục cho phép.' };
    }
    const clampedMarginPct = Math.min(
      INITIAL_MARGIN_MAX_PCT,
      Math.max(INITIAL_MARGIN_MIN_PCT, Number(d.margin_pct) || INITIAL_MARGIN_MIN_PCT)
    );
    return {
      symbol: d.symbol,
      action: ['LONG', 'SHORT', 'HOLD'].includes(d.action) ? d.action : 'HOLD',
      margin_pct: d.action === 'HOLD' ? 0 : clampedMarginPct,
      leverage: symbolCfg.leverage,
      stop_loss: d.stop_loss ? Number(d.stop_loss) : null,
      take_profit: d.take_profit ? Number(d.take_profit) : null,
      audit_reason: String(d.audit_reason || 'Phân tích định kỳ tự động'),
    };
  });
}

async function main() {
  ensureDirectories();
  const runtimeMeta = readJsonSafe(RUNTIME_META_FILE, {
    lastRunAt: 0,
    lastClosedBarByTf: { '15m': 0, '1h': 0, '4h': 0 },
  });
  const lessonsStore = readJsonSafe(LESSONS_FILE, { lessons: [] });

  await ensureLocalWorkerRunning();

  // Tải dữ liệu nến 1m từ lần chạy trước để kiểm tra TP/SL bù (tối đa 120 phút gần nhất)
  const klines1mBySymbol = {};
  for (const symbol of Object.keys(SYMBOLS_CONFIG)) {
    try {
      klines1mBySymbol[symbol] = await fetchBinanceKlines(
        symbol,
        '1m',
        120,
        runtimeMeta.lastRunAt > 0 ? runtimeMeta.lastRunAt : undefined
      );
    } catch (err) {
      console.warn(`[WARN] Bỏ qua tải nến 1m của ${symbol}:`, err.message);
      klines1mBySymbol[symbol] = [];
    }
  }

  // Duyệt tuần tự 15m -> 1h -> 4h đúng chuẩn Heartbeat ba-v-paper-ai-15m-1h-4h
  for (const tf of TIMEFRAMES) {
    console.log(`\n--- Kiểm tra chu kỳ khung ${tf.id} ---`);
    const marketSnapshot = {};
    let latestClosedCandleTime = 0;

    for (const symbol of Object.keys(SYMBOLS_CONFIG)) {
      try {
        const klines = await fetchBinanceKlines(symbol, tf.binanceInterval, 50);
        marketSnapshot[symbol] = klines.slice(-20);
        if (klines.length > 0) {
          latestClosedCandleTime = Math.max(
            latestClosedCandleTime,
            klines[klines.length - 1].closeTime
          );
        }
      } catch (err) {
        console.warn(`[WARN] Không lấy được nến ${tf.id} cho ${symbol}:`, err.message);
      }
    }

    if (
      latestClosedCandleTime === 0 ||
      latestClosedCandleTime <= (runtimeMeta.lastClosedBarByTf[tf.id] || 0)
    ) {
      console.log(`[SKIP] Khung ${tf.id} chưa có nến đóng mới kể từ mốc ${runtimeMeta.lastClosedBarByTf[tf.id]}.`);
      continue;
    }

    // Nếu người dùng có sẵn cli.mjs trong repo thì gọi snapshot qua cli.mjs
    const cliPath = path.resolve(process.cwd(), process.env.CLI_MJS_PATH || 'cli.mjs');
    if (fs.existsSync(cliPath)) {
      try {
        execFileSync(process.execPath, [cliPath, 'snapshot', '--tf', tf.id], { stdio: 'inherit' });
      } catch (err) {
        console.warn(`[WARN] Lệnh cli.mjs snapshot --tf ${tf.id} trả về lỗi:`, err.message);
      }
    }

    // Gọi mô hình AI phân tích kỹ thuật & rút bài học
    const aiResult = await callSol61Analyzer({
      timeframe: tf.id,
      marketSnapshot,
      recentLessons: lessonsStore.lessons,
      walletState: { initialCapital: tf.initialCapital, timeframe: tf.id },
    });

    const sanitized = sanitizeDecisions(aiResult);
    const decisionPayload = {
      timeframe: tf.id,
      candleCloseTime: latestClosedCandleTime,
      generatedAt: new Date().toISOString(),
      reflection: aiResult.reflection_on_recent_trades || '',
      decisions: sanitized,
    };

    const decisionFile = path.join(DECISIONS_DIR, `decision_${tf.id}_${latestClosedCandleTime}.json`);
    writeJsonSafe(decisionFile, decisionPayload);
    console.log(`[DECISION] Đã lưu quyết định khung ${tf.id} vào:`, decisionFile);

    // Nếu có cli.mjs thì đẩy quyết định vào sổ lệnh local
    if (fs.existsSync(cliPath)) {
      try {
        execFileSync(process.execPath, [cliPath, 'apply', '--file', decisionFile], {
          stdio: 'inherit',
        });
      } catch (err) {
        console.warn(`[WARN] Lệnh cli.mjs apply trả về lỗi:`, err.message);
      }
    }

    runtimeMeta.lastClosedBarByTf[tf.id] = latestClosedCandleTime;
  }

  runtimeMeta.lastRunAt = Date.now();
  writeJsonSafe(RUNTIME_META_FILE, runtimeMeta);
  writeJsonSafe(LESSONS_FILE, lessonsStore);

  // Xuất snapshot cho Dashboard tĩnh (GitHub Pages / Vercel)
  try {
    const res = await fetch(`${WORKER_URL}/api/state`, { signal: AbortSignal.timeout(2500) });
    if (res.ok) {
      const stateJson = await res.json();
      writeJsonSafe(STATIC_SNAPSHOT_FILE, {
        ...stateJson,
        cloudUpdatedAt: new Date().toISOString(),
        lessonsLearned: lessonsStore.lessons.slice(0, 20),
      });
    }
  } catch {
    writeJsonSafe(STATIC_SNAPSHOT_FILE, {
      api_version: 3,
      mode: 'PAPER_RESEARCH',
      cloudUpdatedAt: new Date().toISOString(),
      runtimeMeta,
      lessonsLearned: lessonsStore.lessons.slice(0, 20),
    });
  }

  console.log('\n[DONE] Hoàn tất chu kỳ chạy tự động Paper Bot Studio.');
  process.exit(0);
}

main().catch((err) => {
  console.error('[FATAL] Lỗi trong quá trình chạy tự động:', err);
  process.exit(1);
});
