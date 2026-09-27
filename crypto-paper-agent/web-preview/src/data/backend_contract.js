/**
 * Codex Backend Data Contract
 * 
 * Chuẩn cấu trúc dữ liệu trao đổi giữa Python Engine (crypto-paper-agent)
 * và Giao diện Web Preview (Flat Design Console).
 * Đảm bảo phân loại minh bạch nguồn dữ liệu và tuân thủ quy tắc Paper-Only.
 */

export const DATA_CATEGORIES = {
  ILLUSTRATION: {
    id: 'illustration',
    code: 'SYNTHETIC_MOCK',
    labelVi: 'Số liệu minh họa',
    labelEn: 'Synthetic / Illustration',
    descVi: 'Cấu hình tham số ban đầu, kịch bản giả lập.',
    badgeClass: 'badge--illustration',
  },
  HISTORICAL: {
    id: 'historical',
    code: 'HISTORICAL_ARTIFACT',
    labelVi: 'Kết quả lịch sử đã lưu trữ',
    labelEn: 'Historical Artifact',
    descVi: 'Dữ liệu nến 2024 & snapshot PaperBroker có SHA kiểm toán đối chiếu.',
    badgeClass: 'badge--historical',
  },
  DIAGNOSTIC: {
    id: 'diagnostic',
    code: 'DIAGNOSTIC_SAMPLE',
    labelVi: 'Dữ liệu chẩn đoán mẫu',
    labelEn: 'Diagnostic Sample',
    descVi: 'Mẫu kiểm tra độ trễ mạng thực tế 2026 từ Binance Vision.',
    badgeClass: 'badge--diagnostic',
  },
}

export const BACKEND_SAMPLE_CONTRACT = {
  version: '1.2.0-preview',
  mode: 'PAPER_RESEARCH',
  safety: {
    no_live_orders: true,
    no_exchange_keys: true,
    max_leverage_cap: 5,
    stop_loss_enforced: true,
    funding_fail_closed: true,
  },
  runner: {
    status: 'OFFLINE_VIEWER_MODE',
    can_execute_live_trades: false,
    reason: 'Giao diện preview độc lập, không nối daemon thực thi lệnh trực tiếp.',
    allowed_action: 'INSPECT_COMMITTED_REPLAY',
  },
  account_overview: {
    currency: 'USDT',
    initial_equity: 10000.0,
    final_synthetic_equity: 10449.2125,
    total_snapshots: 65,
    max_drawdown_pct: 0.0,
  },
  strategy_descriptions: {
    trend_following: {
      nameVi: 'Bám theo xu hướng',
      nameEn: 'Trend Following',
      conceptVi: 'Vào lệnh khi đường trung bình EMA xác nhận xu hướng tăng/giảm rõ rệt, kết hợp dải biến động ATR để đặt dừng lỗ an toàn.',
      timeframe: '4h / 15m',
      riskTier: 'Normal (2%)',
    },
    breakout_retest: {
      nameVi: 'Phá vỡ cản & Kiểm tra lại',
      nameEn: 'Breakout & Retest',
      conceptVi: 'Đợi giá bứt phá qua các vùng kháng cự/hỗ trợ quan trọng, sau đó kiểm tra lại (retest) thành công mới kích hoạt vị thế.',
      timeframe: '15m / 1m',
      riskTier: 'Normal (2%)',
    },
    smc_liquidity_sweep: {
      nameVi: 'Quét thanh khoản dòng tiền lớn (SMC)',
      nameEn: 'SMC Liquidity Sweep',
      conceptVi: 'Phát hiện các bẫy giá giả mạo quét các mức dừng lỗ của đám đông (Liquidity Hunt) rồi đảo chiều theo dòng tiền thông minh.',
      timeframe: '15m',
      riskTier: 'High (5%)',
    },
    funding_arbitrage: {
      nameVi: 'Khai thác chênh lệch phí Funding',
      nameEn: 'Funding Arbitrage',
      conceptVi: 'Mở rổ vị thế đối ứng cân bằng thị trường để thu phí funding rate định kỳ mỗi 8 tiếng mà không phụ thuộc vào giá tăng hay giảm.',
      timeframe: '8h settlement',
      riskTier: 'Ultra-low (Delta neutral)',
    },
  },
}
