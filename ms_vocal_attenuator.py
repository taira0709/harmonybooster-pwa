import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

# 簡易スイッチ：より強く消したいときに副作用が増えすぎない範囲でブースト
K_MIN   = 1.25   # Mid 最小付近の過剰減算係数（1.25〜1.35くらいが無難）
CENTER_MIN = 0.06  # Mid 最小時のセンター補助キャンセル量（0.06〜0.08）
GATE_THR_DB = -35.0  # ノイズゲートのRMSしきい値（dB）
SAFETY_PEAK = 0.98   # クリップ・セーフティ

def run_file(
    in_path,
    out_path,
    band_low,
    band_high,
    mid_gain_db,
    side_gain_db,
    protect_low_hz,
    protect_high_hz,
    output_gain_db
):
    """
    高速版：STFTを使わず、IIRバンドパス（Butterworth, zero-phase）で mid_band を抽出し、
    mid_proc = mid - k*(1-g_mid)*mid_band を行う。処理はフルベクトル化で高速。

    - WebAudioプレビューの「減算法」に近い手触り（帯域はIIR、位相はfiltfiltでゼロ遅延）
    - Mid最小付近だけ k>1 と Center補助を適用
    - 簡易RMSゲート（移動平均）で残響を軽く整える（最小時のみ）
    - Sideは全帯域でゲイン
    - 最終出力前に HP/LP の保護フィルタ（IIR, zero-phase）
    """

    # ---- 入力 ----
    y, sr = sf.read(in_path, always_2d=True)
    # y: shape (N, C)  → 想定は 2ch（ステレオ）
    if y.shape[1] == 1:
        y = np.repeat(y, 2, axis=1)  # mono→stereo
    y = y.astype(np.float32, copy=False)
    L = y[:, 0]
    R = y[:, 1]

    # ---- M/S 分解 ----
    mid  = (L + R) * 0.5
    side = (L - R) * 0.5

    # ---- dB → 線形 ----
    g_mid  = 10.0 ** (mid_gain_db  / 20.0)
    g_side = 10.0 ** (side_gain_db / 20.0)
    g_out  = 10.0 ** (output_gain_db / 20.0)

    # ---- 帯域の健全化 ----
    bl = float(band_low)
    bh = float(band_high)
    if bh <= bl:
        bh = bl + 1.0
    nyq = sr * 0.5

    # ---- Mid帯域抽出：IIR バンドパス (Butter) → zero-phase ----
    # 4次（2pole×2）の穏やか目。効きが足りなければ order を 6 に。
    order_bp = 4
    low = max(1.0, bl) / nyq
    high = min(nyq - 100.0, bh) / nyq
    high = max(high, low * 1.01)  # ゼロ幅回避
    sos_bp = butter(order_bp, [low, high], btype='band', output='sos')
    mid_band = sosfiltfilt(sos_bp, mid).astype(np.float32, copy=False)

    # ---- 減算法：mid - k*(1 - g_mid)*mid_band ----
    if mid_gain_db <= -80:
        g_mid_use = 0.0
    else:
        g_mid_use = g_mid

    if mid_gain_db <= -75:
        k = K_MIN
    elif mid_gain_db <= -60:
        k = 1.15
    else:
        k = 1.0

    mid_proc = (mid - k * (1.0 - g_mid_use) * mid_band).astype(np.float32, copy=False)

    # ---- 最小付近だけセンター補助キャンセル & 軽ゲート ----
    if mid_gain_db <= -60:
        # センター補助：ほんの少しだけ全域を下げる（副作用とのバランス）
        center_kill = CENTER_MIN if mid_gain_db <= -75 else (CENTER_MIN * 0.66)
        mid_proc *= (1.0 - center_kill)

        # 簡易RMSゲート（移動平均）
        win = 1024
        thr = 10.0 ** (GATE_THR_DB / 20.0)  # ≈ 0.0178
        env = rms_env_fast(mid_proc, win=win)
        gain = np.minimum(1.0, np.maximum(0.0, env / thr)).astype(np.float32, copy=False)
        # ワンポールのARスムージング
        mid_proc *= onepole_smooth(gain, attack=0.30, release=0.05)

    # ---- Side ゲイン ----
    side_proc = (side * g_side).astype(np.float32, copy=False)

    # ---- L/R 合成 ----
    left  = (mid_proc + side_proc).astype(np.float32, copy=False)
    right = (mid_proc - side_proc).astype(np.float32, copy=False)
    y_out = np.stack([left, right], axis=1)  # shape (N, 2)

    # ---- 出力ゲイン ----
    y_out *= g_out

    # ---- ピーク・セーフティ ----
    peak = float(np.max(np.abs(y_out)))
    if peak > SAFETY_PEAK:
        y_out *= (SAFETY_PEAK / peak)

    # ---- 保護フィルタ（IIRで高速）----
    # 低域保護：その周波数以下は“守る”= ここでは余計に削らない方針
    # 高域保護：その周波数以上をローパスで落として耳あたりを守る
    y_out = protect_filters_iir(y_out, sr, protect_low_hz, protect_high_hz)

    # ---- 書き出し ----
    sf.write(out_path, y_out, sr, subtype='FLOAT')  # そのままfloat32で書き出し


# ===== ユーティリティ（高速・ベクトル化） =====

def rms_env_fast(x: np.ndarray, win: int = 1024) -> np.ndarray:
    """移動平均で |x|^2 を平滑化 → sqrt。高速・ベクトル化。"""
    x = x.astype(np.float32, copy=False)
    if win < 2 or win > len(x):
        val = float(np.sqrt(np.mean(x * x) + 1e-12))
        return np.full_like(x, val, dtype=np.float32)
    kernel = np.ones(win, dtype=np.float32) / np.float32(win)
    p = np.convolve(x * x, kernel, mode='same').astype(np.float32, copy=False)
    return np.sqrt(p + 1e-12, dtype=np.float32)

def onepole_smooth(g: np.ndarray, attack=0.30, release=0.05) -> np.ndarray:
    """片ポールのアタック/リリース・スムージング。軽量。"""
    g = g.astype(np.float32, copy=False)
    out = np.empty_like(g)
    prev = np.float32(1.0)
    a = np.float32(attack)
    r = np.float32(release)
    for i in range(len(g)):
        target = g[i]
        coeff = a if target < prev else r
        prev = coeff * target + (1.0 - coeff) * prev
        out[i] = prev
    return out

def protect_filters_iir(y_stereo: np.ndarray, sr: int, low_hz: float, high_hz: float) -> np.ndarray:
    """
    低域保護（HPは“守る”方針なので何もしない）／高域保護（LPで上を少し丸める）。
    IIR (Butter, zero-phase) で高速。必要なときだけ適用。
    """
    y = y_stereo.astype(np.float32, copy=False)
    nyq = sr * 0.5

    # 低域：ここでは “守る” ＝ 追加のHPは掛けない（WebAudioプレビューに整合）
    # もし「超低域のゴソゴソを切りたい」要望があればHPを入れる形でもOK。

    # 高域保護：LP（耳に刺さる帯域の丸め）
    if high_hz is not None and high_hz > 0.0:
        cut = min(float(high_hz), nyq - 100.0) / nyq
        if cut > 0 and cut < 0.99:
            sos_lp = butter(4, cut, btype='low', output='sos')
            y[:, 0] = sosfiltfilt(sos_lp, y[:, 0]).astype(np.float32, copy=False)
            y[:, 1] = sosfiltfilt(sos_lp, y[:, 1]).astype(np.float32, copy=False)
    return y
