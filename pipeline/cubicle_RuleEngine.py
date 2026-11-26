#!/usr/bin/env python3
"""
Venture 03: 老朽キュービクル（高圧受変電設備）・業務用空調
2027年PCB期限 × 2026年工作物アスベスト義務 × 2026年度第三次トップランナー省エネ補助金
規格・損失計算・補助金ルール生成エンジン (cubicle_RuleEngine.py)

本スクリプトは以下の国内法令・JIS規格・補助金公募要領ロジックを構造化し、
決定論的セルフ検証を実行した上で `site/data/equipment_rules.json` を出力します。
1. PCB特別措置法: 2027年(令和9年)3月31日 低濃度PCB廃棄物処分期限 & メーカー別混入可能性年式
2. 改正大気汚染防止法・石綿障害予防規則: 2026年1月1日完全義務化 工作物石綿事前調査
3. 省エネ法・JIS C 4304(油入)/JIS C 4306(モールド): 2026年度 第三次トップランナー変圧器基準の無負荷損・負荷損計算
4. 経産省(SII)省エネルギー投資促進支援事業(1/3補助) + 中小企業加算・47都道府県別上乗せ助成試算
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


VENTURE_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_JSON_PATH = VENTURE_ROOT / "site" / "data" / "equipment_rules.json"
SITE_CTA_PATH = VENTURE_ROOT / "site" / "data" / "cta_config.json"
ROOT_CTA_PATH = VENTURE_ROOT / "data" / "cta_config.json"

HOURS_PER_YEAR = 8760
PCB_LOW_CONC_DEADLINE_ISO = "2027-03-31"
PCB_PRACTICAL_LAB_CUTOFF_ISO = "2026-10-31"
ASBESTOS_ENFORCEMENT_ISO = "2026-01-01"
ASBESTOS_BAN_YEAR = 2006
ASBESTOS_ELECTRONIC_REPORT_MIN_YEN = 1_000_000


MANUFACTURER_RULES: Dict[str, Dict[str, Any]] = {
    "hitachi": {
        "id": "hitachi",
        "name_ja": "日立製作所（日立産機システム）",
        "name_en": "Hitachi",
        "supports_cubicle": True,
        "supports_hvac": True,
        "high_conc_pcb_end_year": 1972,
        "low_conc_pcb_end_year": 1990,
        "oil_refill_caution_end_year": 1993,
        "pcb_window_detail_ja": "高濃度PCBは1972年以前製造分。低濃度PCB混入可能性は変圧器で1990年(平成2年)6月製造分まで、コンデンサで1990年12月製造分までがJEMA・メーカー公表の確認対象です。",
        "aliases": ["日立製作所", "日立産機", "日立", "HITACHI", "アモルファス日立"],
        "model_prefixes": ["SO-", "STO-", "HT-", "SH-", "RAS-", "RPI-", "RPB-"],
    },
    "mitsubishi": {
        "id": "mitsubishi",
        "name_ja": "三菱電機",
        "name_en": "Mitsubishi Electric",
        "supports_cubicle": True,
        "supports_hvac": True,
        "high_conc_pcb_end_year": 1972,
        "low_conc_pcb_end_year": 1990,
        "oil_refill_caution_end_year": 1994,
        "pcb_window_detail_ja": "高濃度PCBは1972年以前製造分。低濃度PCB混入可能性は変圧器・リアクトルで1990年(平成2年)3月製造分まで、計器用変成器で1990年6月製造分まで（絶縁油交換歴がある場合は1994年以前も要採油確認）。",
        "aliases": ["三菱電機", "三菱重工", "三菱", "MITSUBISHI", "スリムER", "パッケージエアコン三菱"],
        "model_prefixes": ["R-", "ST-", "TR-", "PUZ-", "PLZ-", "PFAV-", "PEZX-"],
    },
    "toshiba": {
        "id": "toshiba",
        "name_ja": "東芝（東芝産業機器システム / 旧東京芝浦電気）",
        "name_en": "Toshiba",
        "supports_cubicle": True,
        "supports_hvac": True,
        "high_conc_pcb_end_year": 1972,
        "low_conc_pcb_end_year": 1990,
        "oil_refill_caution_end_year": 1993,
        "pcb_window_detail_ja": "高濃度PCBは1972年以前製造分（旧社名：東京芝浦電気銘板を含む）。低濃度PCB混入可能性は変圧器で1990年(平成2年)3月製造分までが要採油分析対象です。",
        "aliases": ["東京芝浦電気", "芝浦製作所", "東芝産業機器", "東芝キヤリア", "東芝", "TOSHIBA"],
        "model_prefixes": ["TO-", "T-", "ik-", "ROA-", "RUXA-", "AIC-"],
    },
    "fuji": {
        "id": "fuji",
        "name_ja": "富士電機（旧富士電機製造）",
        "name_en": "Fuji Electric",
        "supports_cubicle": True,
        "supports_hvac": False,
        "high_conc_pcb_end_year": 1972,
        "low_conc_pcb_end_year": 1990,
        "oil_refill_caution_end_year": 1993,
        "pcb_window_detail_ja": "高濃度PCBは1972年以前製造分。低濃度PCB混入可能性は変圧器で1989年12月製造分まで、一部油入機器・計器用変成器を含め1990年製造分までが確認対象です。",
        "aliases": ["富士電機製造", "富士電機システムズ", "富士電機", "富士", "FUJI ELECTRIC", "FUJI"],
        "model_prefixes": ["F-", "FT-", "FTR-", "FMS-"],
    },
    "meidensha": {
        "id": "meidensha",
        "name_ja": "明電舎",
        "name_en": "Meidensha",
        "supports_cubicle": True,
        "supports_hvac": False,
        "high_conc_pcb_end_year": 1972,
        "low_conc_pcb_end_year": 1990,
        "oil_refill_caution_end_year": 1993,
        "pcb_window_detail_ja": "高濃度PCBは1972年以前製造分。低濃度PCB混入可能性は油入変圧器・リアクトル等で1990年(平成2年)12月製造分までが採油分析確認対象です。",
        "aliases": ["明電舎", "明電", "MEIDENSHA", "MEIDEN"],
        "model_prefixes": ["M-", "MT-", "B-", "MOR-"],
    },
    "daihen": {
        "id": "daihen",
        "name_ja": "ダイヘン（旧大阪変圧器）",
        "name_en": "Daihen",
        "supports_cubicle": True,
        "supports_hvac": False,
        "high_conc_pcb_end_year": 1972,
        "low_conc_pcb_end_year": 1991,
        "oil_refill_caution_end_year": 1994,
        "pcb_window_detail_ja": "高濃度PCBは1972年以前製造分（旧社名：大阪変圧器銘板に多数該当）。低濃度PCB混入可能性は変圧器1990年11月〜一部油入機器1991年(平成3年)製造分まで確認対象ロットがあります。",
        "aliases": ["大阪変圧器", "ダイヘン", "DAIHEN", "OSAKA TRANSFORMER", "OTC"],
        "model_prefixes": ["PA-", "PF-", "SF-", "U-", "MTR-"],
    },
    "nissin": {
        "id": "nissin",
        "name_ja": "日新電機",
        "name_en": "Nissin Electric",
        "supports_cubicle": True,
        "supports_hvac": False,
        "high_conc_pcb_end_year": 1972,
        "low_conc_pcb_end_year": 1994,
        "oil_refill_caution_end_year": 1994,
        "pcb_window_detail_ja": "高濃度PCBは1972年以前製造分（進相コンデンサ等に多数）。低濃度PCB混入可能性は一部コンデンサ・計器用変成器・油入機器ロットで1994年(平成6年)3月製造分まで要確認対象が含まれます。",
        "aliases": ["日新電機", "日新", "NISSIN ELECTRIC", "NISSIN"],
        "model_prefixes": ["NC-", "NSC-", "NT-", "PV-", "OF-"],
    },
    "aichi": {
        "id": "aichi",
        "name_ja": "愛知電機",
        "name_en": "Aichi Electric",
        "supports_cubicle": True,
        "supports_hvac": False,
        "high_conc_pcb_end_year": 1972,
        "low_conc_pcb_end_year": 1990,
        "oil_refill_caution_end_year": 1993,
        "pcb_window_detail_ja": "高濃度PCBは1972年以前製造分。低濃度PCB混入可能性は1990年(平成2年)11月製造分までの油入変圧器が確認対象です。",
        "aliases": ["愛知電機工作所", "愛知電機", "AICHI ELECTRIC", "AICHI"],
        "model_prefixes": ["AT-", "A-"],
    },
    "daikin": {
        "id": "daikin",
        "name_ja": "ダイキン工業",
        "name_en": "Daikin Industries",
        "supports_cubicle": False,
        "supports_hvac": True,
        "high_conc_pcb_end_year": 1972,
        "low_conc_pcb_end_year": 1990,
        "oil_refill_caution_end_year": 1991,
        "pcb_window_detail_ja": "業務用空調機本体はフロン排出抑制法（R22冷媒全廃・漏洩点検義務）が主対象ですが、1990年以前の旧型大型空調動力盤内の力率改善用コンデンサはPCB確認が必要です。",
        "aliases": ["ダイキン工業", "ダイキン", "DAIKIN", "FIVE STAR ZEAS", "Eco-ZEAS", "スカイエア"],
        "model_prefixes": ["SZRC", "SSRC", "RXYP", "RZP", "FDTV", "FVP", "UC-"],
    },
    "panasonic": {
        "id": "panasonic",
        "name_ja": "パナソニック（旧松下電器産業・三洋電機）",
        "name_en": "Panasonic",
        "supports_cubicle": True,
        "supports_hvac": True,
        "high_conc_pcb_end_year": 1972,
        "low_conc_pcb_end_year": 1990,
        "oil_refill_caution_end_year": 1993,
        "pcb_window_detail_ja": "旧松下電器産業・三洋電機銘板の進相コンデンサ・受変電機器（1990年以前製造）は低濃度PCB要確認、1972年以前は高濃度PCB対象です。",
        "aliases": ["松下電器産業", "松下冷機", "松下電工", "三洋電機", "ナショナル", "パナソニック", "PANASONIC", "SANYO", "NATIONAL"],
        "model_prefixes": ["PA-", "CU-", "CS-", "SPW-"],
    },
    "other": {
        "id": "other",
        "name_ja": "その他国内メーカー・OEM・銘板不明",
        "name_en": "Other / Unidentified",
        "supports_cubicle": True,
        "supports_hvac": True,
        "high_conc_pcb_end_year": 1972,
        "low_conc_pcb_end_year": 1994,
        "oil_refill_caution_end_year": 1994,
        "pcb_window_detail_ja": "メーカー不明またはOEM盤の場合、安全側の法令遵守基準として1972年以前を高濃度PCB疑い、1994年(平成6年)以前製造の油入機器すべてを低濃度PCB採油分析対象として判定します。",
        "aliases": ["北陸電機", "中国電機", "九州変圧器", "指月電機", "帝国コンデンサ", "二井蓄電器", "不明"],
        "model_prefixes": [],
    },
}


# JIS C 4304 (油入変圧器・三相6kV級代表値) 無負荷損 W0 [W] / 定格負荷損 Wc [W]
# 1970年代初期JIS珪素鋼板世代から 2026年度第三次トップランナー基準(およびアモルファス機)までの推移
TRANSFORMER_OIL_LOSS_TABLE: Dict[int, Dict[str, Dict[str, int]]] = {
    50: {
        "era_1970_1980": {"no_load_w": 245, "load_w": 1180},
        "era_1981_1990": {"no_load_w": 198, "load_w": 1020},
        "era_1991_2005": {"no_load_w": 162, "load_w": 910},
        "era_2006_2013": {"no_load_w": 115, "load_w": 780},
        "era_2014_2025": {"no_load_w": 96, "load_w": 695},
        "target_2026_standard": {"no_load_w": 78, "load_w": 610},
        "target_2026_amorphous": {"no_load_w": 36, "load_w": 625},
    },
    75: {
        "era_1970_1980": {"no_load_w": 330, "load_w": 1590},
        "era_1981_1990": {"no_load_w": 268, "load_w": 1380},
        "era_1991_2005": {"no_load_w": 220, "load_w": 1230},
        "era_2006_2013": {"no_load_w": 155, "load_w": 1050},
        "era_2014_2025": {"no_load_w": 128, "load_w": 940},
        "target_2026_standard": {"no_load_w": 104, "load_w": 825},
        "target_2026_amorphous": {"no_load_w": 48, "load_w": 845},
    },
    100: {
        "era_1970_1980": {"no_load_w": 415, "load_w": 1980},
        "era_1981_1990": {"no_load_w": 335, "load_w": 1720},
        "era_1991_2005": {"no_load_w": 275, "load_w": 1530},
        "era_2006_2013": {"no_load_w": 190, "load_w": 1310},
        "era_2014_2025": {"no_load_w": 158, "load_w": 1170},
        "target_2026_standard": {"no_load_w": 128, "load_w": 1030},
        "target_2026_amorphous": {"no_load_w": 60, "load_w": 1055},
    },
    150: {
        "era_1970_1980": {"no_load_w": 565, "load_w": 2680},
        "era_1981_1990": {"no_load_w": 460, "load_w": 2320},
        "era_1991_2005": {"no_load_w": 378, "load_w": 2060},
        "era_2006_2013": {"no_load_w": 260, "load_w": 1770},
        "era_2014_2025": {"no_load_w": 215, "load_w": 1590},
        "target_2026_standard": {"no_load_w": 174, "load_w": 1395},
        "target_2026_amorphous": {"no_load_w": 82, "load_w": 1430},
    },
    200: {
        "era_1970_1980": {"no_load_w": 705, "load_w": 3320},
        "era_1981_1990": {"no_load_w": 575, "load_w": 2880},
        "era_1991_2005": {"no_load_w": 470, "load_w": 2560},
        "era_2006_2013": {"no_load_w": 320, "load_w": 2200},
        "era_2014_2025": {"no_load_w": 265, "load_w": 1975},
        "target_2026_standard": {"no_load_w": 214, "load_w": 1735},
        "target_2026_amorphous": {"no_load_w": 102, "load_w": 1780},
    },
    300: {
        "era_1970_1980": {"no_load_w": 960, "load_w": 4450},
        "era_1981_1990": {"no_load_w": 780, "load_w": 3850},
        "era_1991_2005": {"no_load_w": 640, "load_w": 3420},
        "era_2006_2013": {"no_load_w": 430, "load_w": 2980},
        "era_2014_2025": {"no_load_w": 355, "load_w": 2690},
        "target_2026_standard": {"no_load_w": 285, "load_w": 2360},
        "target_2026_amorphous": {"no_load_w": 135, "load_w": 2420},
    },
    500: {
        "era_1970_1980": {"no_load_w": 1420, "load_w": 6580},
        "era_1981_1990": {"no_load_w": 1150, "load_w": 5720},
        "era_1991_2005": {"no_load_w": 945, "load_w": 5080},
        "era_2006_2013": {"no_load_w": 635, "load_w": 4420},
        "era_2014_2025": {"no_load_w": 525, "load_w": 3990},
        "target_2026_standard": {"no_load_w": 420, "load_w": 3510},
        "target_2026_amorphous": {"no_load_w": 198, "load_w": 3590},
    },
    750: {
        "era_1970_1980": {"no_load_w": 1920, "load_w": 8950},
        "era_1981_1990": {"no_load_w": 1560, "load_w": 7780},
        "era_1991_2005": {"no_load_w": 1280, "load_w": 6920},
        "era_2006_2013": {"no_load_w": 865, "load_w": 6020},
        "era_2014_2025": {"no_load_w": 715, "load_w": 5440},
        "target_2026_standard": {"no_load_w": 575, "load_w": 4780},
        "target_2026_amorphous": {"no_load_w": 270, "load_w": 4890},
    },
    1000: {
        "era_1970_1980": {"no_load_w": 2380, "load_w": 11200},
        "era_1981_1990": {"no_load_w": 1940, "load_w": 9750},
        "era_1991_2005": {"no_load_w": 1590, "load_w": 8680},
        "era_2006_2013": {"no_load_w": 1080, "load_w": 7550},
        "era_2014_2025": {"no_load_w": 895, "load_w": 6820},
        "target_2026_standard": {"no_load_w": 720, "load_w": 5980},
        "target_2026_amorphous": {"no_load_w": 340, "load_w": 6120},
    },
}


def _build_mold_loss_table() -> Dict[int, Dict[str, Dict[str, int]]]:
    """
    JIS C 4306 (モールド変圧器・三相6kV級代表値) 損失テーブルを生成。
    モールド変圧器は難燃エポキシ樹脂絶縁構造のため同容量油入比で無負荷損が約1.28倍、負荷損が約1.14倍となる特性を反映。
    """
    mold_table: Dict[int, Dict[str, Dict[str, int]]] = {}
    for kva, eras in TRANSFORMER_OIL_LOSS_TABLE.items():
        mold_table[kva] = {}
        for era_key, losses in eras.items():
            mold_table[kva][era_key] = {
                "no_load_w": round(losses["no_load_w"] * 1.28),
                "load_w": round(losses["load_w"] * 1.14),
            }
    return mold_table


TRANSFORMER_MOLD_LOSS_TABLE = _build_mold_loss_table()


# 受変電キュービクル・変圧器更新の容量別標準事業費（2026年実勢相場：円）
# equipment_yen: 2026トップランナー変圧器・遮断器・高圧進相コンデンサ・盤一式設備費（SII指定設備1/3補助の対象ベース）
# install_yen: 停電切替工事・クレーン搬出入・耐圧試験・主任技術者立会費
# pcb_disposal_low_yen: 低濃度PCB該当時の採油分析＋収集運搬＋環境省認定無害化処理費目安
# asbestos_survey_yen: 2026年義務化の工作物石綿事前調査＋JIS A 1481分析＋電子報告・養生処分費目安
CUBICLE_CAPEX_BY_KVA: Dict[int, Dict[str, int]] = {
    50: {
        "equipment_yen": 1_650_000,
        "install_yen": 780_000,
        "pcb_disposal_low_yen": 420_000,
        "pcb_disposal_high_yen": 1_150_000,
        "asbestos_survey_yen": 95_000,
        "legacy_annual_maint_penalty_yen": 65_000,
    },
    75: {
        "equipment_yen": 1_980_000,
        "install_yen": 860_000,
        "pcb_disposal_low_yen": 460_000,
        "pcb_disposal_high_yen": 1_280_000,
        "asbestos_survey_yen": 100_000,
        "legacy_annual_maint_penalty_yen": 78_000,
    },
    100: {
        "equipment_yen": 2_350_000,
        "install_yen": 950_000,
        "pcb_disposal_low_yen": 520_000,
        "pcb_disposal_high_yen": 1_450_000,
        "asbestos_survey_yen": 110_000,
        "legacy_annual_maint_penalty_yen": 92_000,
    },
    150: {
        "equipment_yen": 2_950_000,
        "install_yen": 1_150_000,
        "pcb_disposal_low_yen": 610_000,
        "pcb_disposal_high_yen": 1_720_000,
        "asbestos_survey_yen": 120_000,
        "legacy_annual_maint_penalty_yen": 115_000,
    },
    200: {
        "equipment_yen": 3_550_000,
        "install_yen": 1_320_000,
        "pcb_disposal_low_yen": 690_000,
        "pcb_disposal_high_yen": 1_980_000,
        "asbestos_survey_yen": 130_000,
        "legacy_annual_maint_penalty_yen": 140_000,
    },
    300: {
        "equipment_yen": 4_650_000,
        "install_yen": 1_650_000,
        "pcb_disposal_low_yen": 850_000,
        "pcb_disposal_high_yen": 2_450_000,
        "asbestos_survey_yen": 145_000,
        "legacy_annual_maint_penalty_yen": 185_000,
    },
    500: {
        "equipment_yen": 6_900_000,
        "install_yen": 2_350_000,
        "pcb_disposal_low_yen": 1_180_000,
        "pcb_disposal_high_yen": 3_400_000,
        "asbestos_survey_yen": 165_000,
        "legacy_annual_maint_penalty_yen": 270_000,
    },
    750: {
        "equipment_yen": 9_600_000,
        "install_yen": 3_150_000,
        "pcb_disposal_low_yen": 1_550_000,
        "pcb_disposal_high_yen": 4_350_000,
        "asbestos_survey_yen": 185_000,
        "legacy_annual_maint_penalty_yen": 360_000,
    },
    1000: {
        "equipment_yen": 12_400_000,
        "install_yen": 3_950_000,
        "pcb_disposal_low_yen": 1_920_000,
        "pcb_disposal_high_yen": 5_200_000,
        "asbestos_survey_yen": 210_000,
        "legacy_annual_maint_penalty_yen": 460_000,
    },
}


# 業務用パッケージ空調（工場・倉庫・ビル用マルチ）馬力別仕様・APF・更新事業費
HVAC_SPECS_BY_HP: Dict[int, Dict[str, Any]] = {
    3: {
        "cooling_kw": 8.0,
        "apf_by_era": {
            "era_1970_1994": 2.65,
            "era_1995_2003": 3.30,
            "era_2004_2010": 4.25,
            "era_2011_2017": 4.95,
            "era_2018_2025": 5.65,
            "target_2026_top_runner": 6.45,
        },
        "equipment_yen": 540_000,
        "install_yen": 260_000,
        "freon_recovery_yen": 48_000,
        "asbestos_survey_yen": 65_000,
        "legacy_annual_maint_penalty_yen": 32_000,
    },
    5: {
        "cooling_kw": 14.0,
        "apf_by_era": {
            "era_1970_1994": 2.60,
            "era_1995_2003": 3.22,
            "era_2004_2010": 4.15,
            "era_2011_2017": 4.80,
            "era_2018_2025": 5.45,
            "target_2026_top_runner": 6.20,
        },
        "equipment_yen": 760_000,
        "install_yen": 340_000,
        "freon_recovery_yen": 58_000,
        "asbestos_survey_yen": 72_000,
        "legacy_annual_maint_penalty_yen": 45_000,
    },
    8: {
        "cooling_kw": 22.4,
        "apf_by_era": {
            "era_1970_1994": 2.52,
            "era_1995_2003": 3.12,
            "era_2004_2010": 4.02,
            "era_2011_2017": 4.65,
            "era_2018_2025": 5.20,
            "target_2026_top_runner": 5.88,
        },
        "equipment_yen": 1_120_000,
        "install_yen": 460_000,
        "freon_recovery_yen": 75_000,
        "asbestos_survey_yen": 85_000,
        "legacy_annual_maint_penalty_yen": 68_000,
    },
    10: {
        "cooling_kw": 28.0,
        "apf_by_era": {
            "era_1970_1994": 2.48,
            "era_1995_2003": 3.08,
            "era_2004_2010": 3.95,
            "era_2011_2017": 4.55,
            "era_2018_2025": 5.08,
            "target_2026_top_runner": 5.72,
        },
        "equipment_yen": 1_380_000,
        "install_yen": 550_000,
        "freon_recovery_yen": 88_000,
        "asbestos_survey_yen": 92_000,
        "legacy_annual_maint_penalty_yen": 85_000,
    },
    15: {
        "cooling_kw": 42.0,
        "apf_by_era": {
            "era_1970_1994": 2.42,
            "era_1995_2003": 3.00,
            "era_2004_2010": 3.85,
            "era_2011_2017": 4.42,
            "era_2018_2025": 4.92,
            "target_2026_top_runner": 5.50,
        },
        "equipment_yen": 2_050_000,
        "install_yen": 820_000,
        "freon_recovery_yen": 125_000,
        "asbestos_survey_yen": 108_000,
        "legacy_annual_maint_penalty_yen": 120_000,
    },
    20: {
        "cooling_kw": 56.0,
        "apf_by_era": {
            "era_1970_1994": 2.38,
            "era_1995_2003": 2.95,
            "era_2004_2010": 3.78,
            "era_2011_2017": 4.32,
            "era_2018_2025": 4.80,
            "target_2026_top_runner": 5.35,
        },
        "equipment_yen": 2_680_000,
        "install_yen": 1_080_000,
        "freon_recovery_yen": 160_000,
        "asbestos_survey_yen": 120_000,
        "legacy_annual_maint_penalty_yen": 155_000,
    },
    30: {
        "cooling_kw": 85.0,
        "apf_by_era": {
            "era_1970_1994": 2.32,
            "era_1995_2003": 2.88,
            "era_2004_2010": 3.68,
            "era_2011_2017": 4.20,
            "era_2018_2025": 4.68,
            "target_2026_top_runner": 5.18,
        },
        "equipment_yen": 3_950_000,
        "install_yen": 1_580_000,
        "freon_recovery_yen": 220_000,
        "asbestos_survey_yen": 140_000,
        "legacy_annual_maint_penalty_yen": 225_000,
    },
    40: {
        "cooling_kw": 112.0,
        "apf_by_era": {
            "era_1970_1994": 2.28,
            "era_1995_2003": 2.82,
            "era_2004_2010": 3.60,
            "era_2011_2017": 4.12,
            "era_2018_2025": 4.58,
            "target_2026_top_runner": 5.05,
        },
        "equipment_yen": 5_200_000,
        "install_yen": 2_050_000,
        "freon_recovery_yen": 280_000,
        "asbestos_survey_yen": 155_000,
        "legacy_annual_maint_penalty_yen": 290_000,
    },
    50: {
        "cooling_kw": 140.0,
        "apf_by_era": {
            "era_1970_1994": 2.25,
            "era_1995_2003": 2.78,
            "era_2004_2010": 3.55,
            "era_2011_2017": 4.05,
            "era_2018_2025": 4.50,
            "target_2026_top_runner": 4.95,
        },
        "equipment_yen": 6_450_000,
        "install_yen": 2_520_000,
        "freon_recovery_yen": 340_000,
        "asbestos_survey_yen": 175_000,
        "legacy_annual_maint_penalty_yen": 355_000,
    },
}


# 全47都道府県の産業用省エネ設備更新・受変電/空調脱炭素補助金加算パラメータ
# pref_addon_rate_sme: 中小企業向けの都道府県・基礎自治体上乗せ/独自補助率目安（国費と対象経費区分を分けるか独自枠活用時の実質加算率）
# pref_cap_yen: 自治体加算の上限目安
PREFECTURE_SUBSIDIES: List[Dict[str, Any]] = [
    {"code": "01", "name": "北海道", "program_name": "北海道中小企業省エネ・脱炭素設備導入支援", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "02", "name": "青森県", "program_name": "あおもり脱炭素経営促進設備導入補助", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_000_000},
    {"code": "03", "name": "岩手県", "program_name": "岩手県事業者向け省エネルギー設備更新支援", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_000_000},
    {"code": "04", "name": "宮城県", "program_name": "みやぎ二酸化炭素排出削減設備導入補助金", "pref_addon_rate_sme": 0.12, "pref_cap_yen": 2_000_000},
    {"code": "05", "name": "秋田県", "program_name": "秋田県脱炭素社会推進設備投資支援事業", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_200_000},
    {"code": "06", "name": "山形県", "program_name": "山形県中小企業省エネ・再エネ設備導入補助", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_200_000},
    {"code": "07", "name": "福島県", "program_name": "福島県中小企業等省エネ設備更新補助金", "pref_addon_rate_sme": 0.12, "pref_cap_yen": 1_800_000},
    {"code": "08", "name": "茨城県", "program_name": "茨城県中小企業脱炭素化促進設備導入補助", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "09", "name": "栃木県", "program_name": "とちぎ省エネ設備導入促進事業補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "10", "name": "群馬県", "program_name": "群馬県グリーンイノベーション省エネ投資支援", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "11", "name": "埼玉県", "program_name": "埼玉県中小企業CO2排出削減設備導入補助金", "pref_addon_rate_sme": 0.15, "pref_cap_yen": 2_500_000},
    {"code": "12", "name": "千葉県", "program_name": "千葉県脱炭素化促進設備導入支援補助金", "pref_addon_rate_sme": 0.12, "pref_cap_yen": 2_000_000},
    {"code": "13", "name": "東京都", "program_name": "クール・ネット東京 省エネ・非フロン機器導入助成", "pref_addon_rate_sme": 0.22, "pref_cap_yen": 5_000_000},
    {"code": "14", "name": "神奈川県", "program_name": "神奈川県中小企業エネルギー効率化・脱炭素助成", "pref_addon_rate_sme": 0.15, "pref_cap_yen": 3_000_000},
    {"code": "15", "name": "新潟県", "program_name": "新潟県事業者向け脱炭素設備投資支援補助", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "16", "name": "富山県", "program_name": "富山県中小企業省エネ設備更新応援補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "17", "name": "石川県", "program_name": "いしかわカーボンニュートラル設備導入補助", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "18", "name": "福井県", "program_name": "福井県工場・事業場省エネ設備更新補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "19", "name": "山梨県", "program_name": "やまなし脱炭素経営設備導入支援補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_200_000},
    {"code": "20", "name": "長野県", "program_name": "長野県中小企業ゼロカーボン設備投資補助金", "pref_addon_rate_sme": 0.12, "pref_cap_yen": 1_800_000},
    {"code": "21", "name": "岐阜県", "program_name": "岐阜県省エネ・脱炭素設備更新促進補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "22", "name": "静岡県", "program_name": "静岡県中小企業脱炭素経営設備導入補助金", "pref_addon_rate_sme": 0.12, "pref_cap_yen": 2_000_000},
    {"code": "23", "name": "愛知県", "program_name": "あいち脱炭素経営・高効率設備更新促進補助金", "pref_addon_rate_sme": 0.15, "pref_cap_yen": 3_000_000},
    {"code": "24", "name": "三重県", "program_name": "三重県事業者省エネルギー投資支援補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "25", "name": "滋賀県", "program_name": "しがCO2ネットゼロ産業設備導入補助金", "pref_addon_rate_sme": 0.12, "pref_cap_yen": 1_800_000},
    {"code": "26", "name": "京都府", "program_name": "京都府中小企業省エネ・脱炭素推進補助金", "pref_addon_rate_sme": 0.12, "pref_cap_yen": 2_000_000},
    {"code": "27", "name": "大阪府", "program_name": "大阪府中小事業者脱炭素化・高効率設備導入補助", "pref_addon_rate_sme": 0.15, "pref_cap_yen": 3_000_000},
    {"code": "28", "name": "兵庫県", "program_name": "ひょうご産業脱炭素化設備導入支援事業", "pref_addon_rate_sme": 0.12, "pref_cap_yen": 2_200_000},
    {"code": "29", "name": "奈良県", "program_name": "奈良県中小企業省エネルギー設備導入補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_200_000},
    {"code": "30", "name": "和歌山県", "program_name": "和歌山県脱炭素経営促進設備更新補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_200_000},
    {"code": "31", "name": "鳥取県", "program_name": "鳥取県省エネ・脱炭素設備導入支援補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_000_000},
    {"code": "32", "name": "島根県", "program_name": "島根県中小企業エネルギーコスト削減設備補助", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_000_000},
    {"code": "33", "name": "岡山県", "program_name": "おかやま事業者省エネ設備更新支援補助金", "pref_addon_rate_sme": 0.12, "pref_cap_yen": 1_800_000},
    {"code": "34", "name": "広島県", "program_name": "広島県カーボンニュートラル設備投資促進補助", "pref_addon_rate_sme": 0.12, "pref_cap_yen": 2_000_000},
    {"code": "35", "name": "山口県", "program_name": "やまぐち産業脱炭素化設備導入支援補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "36", "name": "徳島県", "program_name": "徳島県中小企業GX・省エネ設備更新補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_200_000},
    {"code": "37", "name": "香川県", "program_name": "かがわ省エネ・脱炭素設備導入促進補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_200_000},
    {"code": "38", "name": "愛媛県", "program_name": "愛媛県中小企業省エネルギー設備更新補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "39", "name": "高知県", "program_name": "高知県脱炭素経営推進設備導入支援補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_000_000},
    {"code": "40", "name": "福岡県", "program_name": "福岡県中小企業省エネ・脱炭素設備投資補助金", "pref_addon_rate_sme": 0.14, "pref_cap_yen": 2_500_000},
    {"code": "41", "name": "佐賀県", "program_name": "佐賀県事業者向け省エネルギー設備導入補助", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_200_000},
    {"code": "42", "name": "長崎県", "program_name": "ながさきゼロカーボン設備投資支援補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_200_000},
    {"code": "43", "name": "熊本県", "program_name": "熊本県中小企業省エネ設備更新促進補助金", "pref_addon_rate_sme": 0.12, "pref_cap_yen": 1_800_000},
    {"code": "44", "name": "大分県", "program_name": "大分県産業脱炭素・高効率設備導入補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_500_000},
    {"code": "45", "name": "宮崎県", "program_name": "宮崎県中小企業省エネ・再エネ設備導入補助", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_200_000},
    {"code": "46", "name": "鹿児島県", "program_name": "かごしま脱炭素経営設備更新支援補助金", "pref_addon_rate_sme": 0.10, "pref_cap_yen": 1_200_000},
    {"code": "47", "name": "沖縄県", "program_name": "沖縄県事業者省エネルギー設備導入支援事業", "pref_addon_rate_sme": 0.12, "pref_cap_yen": 1_500_000},
]


SAMPLE_NAMEPLATES: List[Dict[str, str]] = [
    {
        "id": "sample_cubicle_1987",
        "label": "サンプル①：1987年製 三菱電機 300kVA 油入変圧器",
        "raw_text": "三相変圧器 銘板\n形式 R-300A  定格容量 300 kVA\n一次電圧 6600V  二次電圧 210V  周波数 50Hz\n冷却方式 油入自冷式 (JIS C 4304)  絶縁油量 215L\n製造年月 昭和62年8月  株式会社三菱電機 名古屋製作所",
    },
    {
        "id": "sample_cubicle_1992_nissin",
        "label": "サンプル②：1992年製 日新電機 500kVA 高圧受電盤",
        "raw_text": "高圧受変電設備 キュービクル式\n主変圧器容量 500KVA 三相3線 6.6kV\n力率改善用高圧進相コンデンサ内蔵 油入式\n型式 NC-500H  平成4年11月製造\n日新電機株式会社 京都工場",
    },
    {
        "id": "sample_hvac_1999_daikin",
        "label": "サンプル③：1999年製 ダイキン 20馬力 R22業務用空調",
        "raw_text": "空冷ヒートポンプ式パッケージエアコン 室外ユニット\n機種名 RXYP560A (20馬力相当 / 冷房能力 56.0kW)\n冷媒 R22 充填量 14.5kg  電源 三相200V\n1999年製  ダイキン工業株式会社",
    },
]


def classify_transformer_era(year: int) -> str:
    if year <= 1980:
        return "era_1970_1980"
    if year <= 1990:
        return "era_1981_1990"
    if year <= 2005:
        return "era_1991_2005"
    if year <= 2013:
        return "era_2006_2013"
    return "era_2014_2025"


def classify_hvac_era(year: int) -> str:
    if year <= 1994:
        return "era_1970_1994"
    if year <= 2003:
        return "era_1995_2003"
    if year <= 2010:
        return "era_2004_2010"
    if year <= 2017:
        return "era_2011_2017"
    return "era_2018_2025"


def evaluate_pcb_risk(
    equipment_type: str,
    manufacturer_id: str,
    manufacturing_year: int,
    insulation_type: str = "oil",
) -> Dict[str, Any]:
    maker = MANUFACTURER_RULES.get(manufacturer_id, MANUFACTURER_RULES["other"])
    high_end = maker["high_conc_pcb_end_year"]
    low_end = maker["low_conc_pcb_end_year"]
    refill_end = maker["oil_refill_caution_end_year"]

    if equipment_type == "hvac":
        if manufacturing_year <= high_end:
            return {
                "severity": "critical",
                "code": "HIGH_CONC_AUX_CAPACITOR_RISK",
                "badge_ja": "【最重大】高濃度PCBコンデンサ混在リスク＋R22冷媒",
                "analysis_required": True,
                "summary_ja": f"{manufacturing_year}年製の大型空調設備は動力盤内の力率改善コンデンサに高濃度PCBが含まれる可能性があり、直ちに銘板確認と隔離が必要です。",
            }
        if manufacturing_year <= low_end:
            return {
                "severity": "high",
                "code": "LOW_CONC_AUX_CAPACITOR_AND_R22",
                "badge_ja": "【要確認】動力盤内コンデンサPCB確認（2027年3月期限）＋R22全廃機",
                "analysis_required": True,
                "summary_ja": f"{manufacturing_year}年製のため、付属動力盤の油入コンデンサが2027年3月31日低濃度PCB処分期限の対象か確認が必要です。冷媒R22も供給終了しています。",
            }
        if manufacturing_year <= 2003:
            return {
                "severity": "medium",
                "code": "R22_FREON_PHASEOUT_RISK",
                "badge_ja": "PCB原則対象外 ／ 【注意】R22旧フロン全廃・部品供給終了世代",
                "analysis_required": False,
                "summary_ja": "機器本体のPCB含有リスクは低いですが、HCFC(R22)冷媒の生産終了により圧縮機故障・ガス漏洩時の修理不能リスクが極めて高い世代です。",
            }
        return {
            "severity": "low",
            "code": "PCB_CLEAR_HVAC",
            "badge_ja": "PCB規制対象外（フロン排出抑制法の定期点検対象）",
            "analysis_required": False,
            "summary_ja": "1995年以降製造のためPCB対象外です。フロン排出抑制法に基づく簡易点検・定期点検および更新時のフロン回収証明書交付を行ってください。",
        }

    # Cubicle / Transformer
    if insulation_type == "mold" and manufacturing_year > high_end:
        return {
            "severity": "low",
            "code": "MOLD_DRY_TYPE_CLEAR",
            "badge_ja": "乾式（モールド変圧器）のため絶縁油PCB対象外（※盤内コンデンサのみ銘板確認）",
            "analysis_required": False,
            "summary_ja": "モールド変圧器本体は絶縁油を使用しないためPCB汚染対象外です。ただしキュービクル内の高圧進相コンデンサ(SC)が1990年以前製でないか併せて確認してください。",
        }

    if manufacturing_year <= high_end:
        return {
            "severity": "critical",
            "code": "HIGH_CONC_PCB_EXPIRED",
            "badge_ja": "【緊急法令対応】高濃度PCB該当リスク（法定処分期限経過済）",
            "analysis_required": True,
            "summary_ja": f"{maker['name_ja']}の{manufacturing_year}年製機器は1972年以前製造の高濃度PCB使用電気工作物に該当する可能性が高く、電気主任技術者および都道府県環境部局への即時相談が必要です。",
        }

    if manufacturing_year <= low_end:
        return {
            "severity": "high",
            "code": "LOW_CONC_PCB_2027_DEADLINE",
            "badge_ja": f"【2027年3月31日処分期限】低濃度PCB混入可能性あり（{maker['name_ja']}：{low_end}年以前対象）",
            "analysis_required": True,
            "summary_ja": f"{maker['pcb_window_detail_ja']} 絶縁油のPCB濃度分析（基準0.5mg/kg超で該当）および2027年3月31日までの無害化処理完了が法定義務です。",
        }

    if manufacturing_year <= refill_end:
        return {
            "severity": "medium",
            "code": "OIL_REFILL_HISTORY_CHECK",
            "badge_ja": f"【準注意】出荷時PCB不含世代／{refill_end}年以前の再生絶縁油補油歴のみ要確認",
            "analysis_required": True,
            "summary_ja": f"{maker['name_ja']}の出荷時点基準（{low_end}年）以降ですが、{refill_end}年以前に現地で絶縁油交換・補油を行った履歴がある場合は廃棄時に採油分析が求められます。",
        }

    return {
        "severity": "low",
        "code": "PCB_CLEAR_POST_1995",
        "badge_ja": "PCB規制対象外（1995年以降の非PCB確定世代）",
        "analysis_required": False,
        "summary_ja": f"{manufacturing_year}年製造のためPCB混入リスクは原則ありません（廃棄時は通常の産業廃棄物／特別管理産業廃棄物フローで処理可能）。",
    }


def evaluate_asbestos_requirement(manufacturing_year: int, total_project_yen: int) -> Dict[str, Any]:
    electronic_report_needed = total_project_yen >= ASBESTOS_ELECTRONIC_REPORT_MIN_YEN
    if manufacturing_year <= ASBESTOS_BAN_YEAR:
        return {
            "required_physical_survey": True,
            "severity": "high",
            "badge_ja": "【2026年1月義務化】工作物石綿事前調査者による現地・分析調査 必須",
            "electronic_report_required": electronic_report_needed,
            "summary_ja": (
                f"{manufacturing_year}年製（2006年8月以前の石綿全面禁止前）のため、2026年1月施行の改正大気汚染防止法・石綿則により、"
                "更新・撤去工事前に「工作物石綿事前調査者」等の有資格者によるフランジガスケット・パッキン・耐火パテ・断熱材・塗膜の事前調査（またはみなし含有養生）が完全義務化されています。"
                + ("また請負金額100万円以上のためGビズIDによる労働基準監督署・自治体への電子報告が義務です。" if electronic_report_needed else "")
            ),
        }
    return {
        "required_physical_survey": False,
        "severity": "low",
        "badge_ja": "書面事前調査（2006年9月以降着工の銘板・竣工図確認＋記録3年保存）で対応可",
        "electronic_report_required": electronic_report_needed,
        "summary_ja": (
            f"{manufacturing_year}年製（2006年9月石綿全面禁止以降）のため試料採取分析は不要ですが、"
            "製造年銘板・設計図書による書面調査記録の作成・3年間保存"
            + ("および請負金額100万円以上のGビズID電子報告" if electronic_report_needed else "")
            + "は法定手続きとして実施が必要です。"
        ),
    }


def calculate_transformer_annual_loss_kwh(
    capacity_kva: int,
    manufacturing_year: int,
    load_factor_pct: float,
    insulation_type: str = "oil",
    use_amorphous_2026: bool = False,
) -> Dict[str, Any]:
    table = TRANSFORMER_MOLD_LOSS_TABLE if insulation_type == "mold" else TRANSFORMER_OIL_LOSS_TABLE
    nearest_kva = min(table.keys(), key=lambda k: abs(k - capacity_kva))
    scale = capacity_kva / float(nearest_kva) if nearest_kva > 0 else 1.0

    era_key = classify_transformer_era(manufacturing_year)
    target_key = "target_2026_amorphous" if use_amorphous_2026 else "target_2026_standard"

    legacy_spec = table[nearest_kva][era_key]
    modern_spec = table[nearest_kva][target_key]

    # 変圧器損失は容量の約0.75乗則に近似するが標準容量一致時は厳密テーブル値を使用
    loss_scale = 1.0 if capacity_kva == nearest_kva else (scale ** 0.78)
    legacy_w0 = round(legacy_spec["no_load_w"] * loss_scale, 1)
    legacy_wc = round(legacy_spec["load_w"] * loss_scale, 1)
    modern_w0 = round(modern_spec["no_load_w"] * loss_scale, 1)
    modern_wc = round(modern_spec["load_w"] * loss_scale, 1)

    m_ratio = max(0.05, min(1.20, load_factor_pct / 100.0))
    legacy_total_w = legacy_w0 + (m_ratio ** 2) * legacy_wc
    modern_total_w = modern_w0 + (m_ratio ** 2) * modern_wc

    legacy_kwh = round((legacy_total_w / 1000.0) * HOURS_PER_YEAR)
    modern_kwh = round((modern_total_w / 1000.0) * HOURS_PER_YEAR)
    saved_kwh = max(0, legacy_kwh - modern_kwh)
    reduction_pct = round((saved_kwh / legacy_kwh) * 100.0, 1) if legacy_kwh > 0 else 0.0

    return {
        "matched_standard_kva": nearest_kva,
        "legacy_era": era_key,
        "target_spec": target_key,
        "legacy_no_load_w": legacy_w0,
        "legacy_load_w": legacy_wc,
        "modern_no_load_w": modern_w0,
        "modern_load_w": modern_wc,
        "legacy_annual_loss_kwh": legacy_kwh,
        "modern_annual_loss_kwh": modern_kwh,
        "annual_saved_kwh": saved_kwh,
        "loss_reduction_pct": reduction_pct,
    }


def calculate_subsidy_and_payback(
    equipment_yen: int,
    install_yen: int,
    compliance_extra_yen: int,
    annual_elec_saved_yen: int,
    annual_maint_saved_yen: int,
    prefecture_code: str,
    is_sme: bool,
) -> Dict[str, Any]:
    gross_capex = equipment_yen + install_yen + compliance_extra_yen
    # 経産省 SII 省エネルギー投資促進支援事業（指定設備導入事業：高効率変圧器 / 業務用エアコン 設備費の1/3以内）
    sii_base_subsidy = round(equipment_yen / 3.0)

    pref = next((p for p in PREFECTURE_SUBSIDIES if p["code"] == prefecture_code), PREFECTURE_SUBSIDIES[12])
    # 中小企業省力化・自治体独自脱炭素枠（付帯工事・非フロン/高効率加算または都道府県独自枠の優位分）
    sme_pref_addon = 0
    if is_sme:
        raw_addon = round((equipment_yen + install_yen) * pref["pref_addon_rate_sme"])
        sme_pref_addon = min(raw_addon, pref["pref_cap_yen"])

    # 法令上の実質補助上限ガード（総事業費の2/3を超えないよう保守的にキャップ）
    total_subsidy = min(sii_base_subsidy + sme_pref_addon, round(gross_capex * 0.66))
    net_capex = max(0, gross_capex - total_subsidy)

    annual_total_benefit = max(1, annual_elec_saved_yen + annual_maint_saved_yen)
    payback_years = round(net_capex / float(annual_total_benefit), 1)

    return {
        "gross_capex_yen": gross_capex,
        "sii_national_subsidy_yen": sii_base_subsidy,
        "prefecture_sme_addon_yen": sme_pref_addon,
        "total_subsidy_yen": total_subsidy,
        "net_capex_yen": net_capex,
        "annual_total_benefit_yen": annual_total_benefit,
        "payback_years": payback_years,
        "prefecture_program_name": pref["program_name"],
    }


def parse_nameplate_text(raw_text: str) -> Dict[str, Any]:
    """
    銘板OCRテキストから設備種別・メーカー・製造年（昭和/平成/令和/西暦対応）・容量（kVA/馬力/kW換算）・絶縁/冷媒方式を抽出。
    """
    normalized = unicodedata.normalize("NFKC", raw_text)
    upper_text = normalized.upper()
    reasons: List[str] = []

    # 1. 設備種別判定
    hvac_keywords = ["エアコン", "パッケージ", "室外", "冷媒", "R22", "R410A", "R32", "ヒートポンプ", "馬力", "空冷"]
    cubicle_keywords = ["変圧器", "キュービクル", "受変電", "KVA", "6600V", "6.6KV", "絶縁油", "モールド", "進相コンデンサ"]
    is_hvac = any(k in upper_text for k in hvac_keywords) and not any(k in upper_text for k in ["変圧器", "キュービクル", "6600V"])
    equipment_type = "hvac" if is_hvac else "cubicle"
    reasons.append(f"設備種別: {'業務用パッケージ空調' if equipment_type == 'hvac' else '高圧受変電キュービクル・変圧器'}")

    # 2. メーカー判定（旧社名エイリアス優先）
    detected_maker = "other"
    for maker_id, mdata in MANUFACTURER_RULES.items():
        if maker_id == "other":
            continue
        for alias in mdata["aliases"]:
            if alias.upper() in upper_text:
                detected_maker = maker_id
                reasons.append(f"メーカー認識: 「{alias}」→ {mdata['name_ja']}")
                break
        if detected_maker != "other":
            break

    # 3. 製造年判定（昭和・平成・令和・西暦 — R22/R32等の冷媒記号や型番との誤認防止ガード付き）
    detected_year: Optional[int] = None
    m_showa = re.search(r"昭和\s*(\d{1,2})\s*年?", upper_text) or re.search(
        r"(?<![A-Z0-9-])S\s*(\d{2})(?:\s*年|\.\d{1,2})", upper_text
    )
    m_heisei = re.search(r"平成\s*(\d{1,2}|元)\s*年?", upper_text) or re.search(
        r"(?<![A-Z0-9-])H\s*(\d{1,2})(?:\s*年|\.\d{1,2})", upper_text
    )
    m_reiwa = re.search(r"令和\s*(\d{1,2}|元)\s*年?", upper_text) or re.search(
        r"(?<![A-Z0-9-])R\s*([1-9])(?:\s*年|\.\d{1,2})", upper_text
    )
    m_west = re.search(r"(19[6-9]\d|20[0-2]\d)\s*年", normalized) or re.search(
        r"\b(19[6-9]\d|20[0-2]\d)\b", normalized
    )

    if m_showa:
        yr_num = int(m_showa.group(1))
        detected_year = 1925 + yr_num
        reasons.append(f"和暦変換: 昭和{yr_num}年 → 西暦{detected_year}年")
    elif m_heisei:
        val = m_heisei.group(1)
        yr_num = 1 if val == "元" else int(val)
        detected_year = 1988 + yr_num
        reasons.append(f"和暦変換: 平成{val}年 → 西暦{detected_year}年")
    elif m_reiwa:
        val = m_reiwa.group(1)
        yr_num = 1 if val == "元" else int(val)
        detected_year = 2018 + yr_num
        reasons.append(f"和暦変換: 令和{val}年 → 西暦{detected_year}年")
    elif m_west:
        detected_year = int(m_west.group(1))
        reasons.append(f"製造年抽出: 西暦{detected_year}年")

    if detected_year is not None:
        detected_year = max(1970, min(2025, detected_year))

    # 4. 容量判定 (kVA or 馬力 / kW)
    detected_capacity: Optional[int] = None
    if equipment_type == "cubicle":
        m_kva = re.search(r"(\d{2,4})\s*KVA", upper_text)
        if m_kva:
            detected_capacity = int(m_kva.group(1))
            reasons.append(f"定格容量抽出: {detected_capacity} kVA")
    else:
        m_hp = re.search(r"(\d{1,3})\s*(?:馬力|HP)", upper_text)
        m_kw = re.search(r"(\d{1,3}(?:\.\d+)?)\s*KW", upper_text)
        if m_hp:
            detected_capacity = int(m_hp.group(1))
            reasons.append(f"空調馬力抽出: {detected_capacity} 馬力")
        elif m_kw:
            kw_val = float(m_kw.group(1))
            detected_capacity = max(3, round(kw_val / 2.8))
            reasons.append(f"冷房能力換算: {kw_val} kW → 約{detected_capacity} 馬力相当")

    # 5. 絶縁方式（油入 vs モールド）
    insulation_type = "mold" if ("モールド" in normalized or "乾式" in normalized or "JIS C 4306" in upper_text) else "oil"

    return {
        "equipment_type": equipment_type,
        "manufacturer_id": detected_maker,
        "manufacturing_year": detected_year,
        "capacity": detected_capacity,
        "insulation_type": insulation_type,
        "reasons": reasons,
    }


def build_rules_payload() -> Dict[str, Any]:
    return {
        "schema_version": "2026.03",
        "generated_by": "pipeline/cubicle_RuleEngine.py",
        "regulatory_deadlines": {
            "pcb_low_conc_disposal_deadline": PCB_LOW_CONC_DEADLINE_ISO,
            "pcb_practical_sampling_deadline": PCB_PRACTICAL_LAB_CUTOFF_ISO,
            "pcb_law_reference": "ポリ塩化ビフェニル廃棄物の適正な処理の推進に関する特別措置法（PCB特措法）第10条・施行令（計画的処理完了期限：2027年3月31日）",
            "pcb_penalty_summary": "改善命令違反時：3年以下の懲役若しくは1,000万円以下の罰金（又は併科）。2027年4月以降は環境省認定無害化処理施設での受入終了リスクあり。",
            "asbestos_workplace_enforcement_date": ASBESTOS_ENFORCEMENT_ISO,
            "asbestos_ban_threshold_year": ASBESTOS_BAN_YEAR,
            "asbestos_electronic_report_min_yen": ASBESTOS_ELECTRONIC_REPORT_MIN_YEN,
            "asbestos_law_reference": "改正大気汚染防止法・石綿障害予防規則（2026年1月1日施行：特定工作物・電気設備・空調設備の有資格者による事前調査完全義務化）",
            "top_runner_2026_reference": "エネルギーの使用の合理化及び非化石エネルギーへの転換等に関する法律（省エネ法）2026年度目標 第三次トップランナー変圧器基準（JIS C 4304 油入変圧器 / JIS C 4306 モールド変圧器）",
            "co2_emission_factor_kg_per_kwh": 0.438,
        },
        "manufacturers": MANUFACTURER_RULES,
        "transformer_specs": {
            "standard_capacities_kva": sorted(list(TRANSFORMER_OIL_LOSS_TABLE.keys())),
            "hours_per_year": HOURS_PER_YEAR,
            "oil_jis_c_4304": {str(k): v for k, v in TRANSFORMER_OIL_LOSS_TABLE.items()},
            "mold_jis_c_4306": {str(k): v for k, v in TRANSFORMER_MOLD_LOSS_TABLE.items()},
            "capex_by_kva": {str(k): v for k, v in CUBICLE_CAPEX_BY_KVA.items()},
            "era_labels": {
                "era_1970_1980": "1970〜1980年製（初期JIS珪素鋼板世代）",
                "era_1981_1990": "1981〜1990年製（旧JIS標準・低濃度PCB要確認世代）",
                "era_1991_2005": "1991〜2005年製（トップランナー導入前世代）",
                "era_2006_2013": "2006〜2013年製（第一次トップランナー基準世代）",
                "era_2014_2025": "2014〜2025年製（第二次トップランナー基準世代）",
                "target_2026_standard": "2026年度 第三次トップランナー基準適合変圧器",
                "target_2026_amorphous": "2026年度 第三次トップランナー 超高効率アモルファス変圧器",
            },
        },
        "hvac_specs": {
            "standard_capacities_hp": sorted(list(HVAC_SPECS_BY_HP.keys())),
            "annual_full_load_equiv_hours_base": 2600,
            "specs_by_hp": {str(k): v for k, v in HVAC_SPECS_BY_HP.items()},
            "era_labels": {
                "era_1970_1994": "1970〜1994年製（R22定速機・動力盤PCB注意世代）",
                "era_1995_2003": "1995〜2003年製（R22/R407C旧インバータ・石綿調査世代）",
                "era_2004_2010": "2004〜2010年製（R410A初期インバータ世代）",
                "era_2011_2017": "2011〜2017年製（R410A中期インバータ世代）",
                "era_2018_2025": "2018〜2025年製（R32現行インバータ世代）",
                "target_2026_top_runner": "2026年最新 R32超高効率インバータ空調機",
            },
        },
        "subsidy_rules": {
            "national_sii": {
                "program_name": "経済産業省（SII）省エネルギー投資促進支援事業（III 指定設備導入事業：高効率変圧器・業務用エアコン）",
                "equipment_subsidy_rate": 0.333333,
                "factory_wide_sme_alt_rate": 0.50,
                "max_combined_subsidy_ratio": 0.66,
                "tax_incentive_note": "中小企業経営強化税制（即時償却または取得価額10%税額控除※資本金3,000万円以下）との活用検討も可能（※国庫補助金との圧縮記帳ルールは顧問税理士確認）。",
            },
            "prefectures": PREFECTURE_SUBSIDIES,
        },
        "sample_nameplates": SAMPLE_NAMEPLATES,
    }


def run_self_validation(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    logs: List[str] = []

    # 1. 必須メーカー7社の網羅性とPCB年式チェック
    required_makers = ["hitachi", "mitsubishi", "toshiba", "fuji", "meidensha", "daihen", "nissin"]
    for mk in required_makers:
        assert mk in payload["manufacturers"], f"Missing required manufacturer: {mk}"
        m_info = payload["manufacturers"][mk]
        assert m_info["high_conc_pcb_end_year"] == 1972, f"{mk} high-conc year must be 1972"
        assert 1989 <= m_info["low_conc_pcb_end_year"] <= 1994, f"{mk} low-conc year out of expected range"
    logs.append(f"[OK] Verified 7 core electrical makers + HVAC makers ({len(payload['manufacturers'])} total).")

    # 2. PCB判定ロジックの境界値検証
    r_1971 = evaluate_pcb_risk("cubicle", "toshiba", 1971, "oil")
    assert r_1971["severity"] == "critical" and r_1971["analysis_required"] is True
    r_1988 = evaluate_pcb_risk("cubicle", "hitachi", 1988, "oil")
    assert r_1988["severity"] == "high" and r_1988["code"] == "LOW_CONC_PCB_2027_DEADLINE"
    r_1993_nissin = evaluate_pcb_risk("cubicle", "nissin", 1993, "oil")
    assert r_1993_nissin["severity"] == "high", "Nissin 1993 must trigger low-conc PCB check window"
    r_2012 = evaluate_pcb_risk("cubicle", "mitsubishi", 2012, "oil")
    assert r_2012["severity"] == "low" and r_2012["analysis_required"] is False
    logs.append("[OK] Verified pre-1972 high-conc vs 1990/1991/1994 maker-specific low-conc PCB boundaries.")

    # 3. 2026年1月工作物アスベスト事前調査ロジック検証
    asb_2004 = evaluate_asbestos_requirement(2004, 4_500_000)
    assert asb_2004["required_physical_survey"] is True and asb_2004["electronic_report_required"] is True
    asb_2015 = evaluate_asbestos_requirement(2015, 4_500_000)
    assert asb_2015["required_physical_survey"] is False and asb_2015["electronic_report_required"] is True
    logs.append("[OK] Verified 2026-01-01 workplace asbestos pre-2006 inspection & >=1M JPY electronic report rules.")

    # 4. 50kVA〜1000kVA 全容量における年代別損失の単調減少性と2026トップランナー省エネ効果検証
    era_order = [
        "era_1970_1980",
        "era_1981_1990",
        "era_1991_2005",
        "era_2006_2013",
        "era_2014_2025",
        "target_2026_standard",
    ]
    for kva in TRANSFORMER_OIL_LOSS_TABLE.keys():
        prev_loss_w = float("inf")
        for era in era_order:
            spec = TRANSFORMER_OIL_LOSS_TABLE[kva][era]
            eff_w = spec["no_load_w"] + (0.40 ** 2) * spec["load_w"]
            assert eff_w < prev_loss_w, f"Non-monotonic loss at {kva}kVA {era}"
            prev_loss_w = eff_w

    sim_300 = calculate_transformer_annual_loss_kwh(300, 1987, 45.0, "oil", use_amorphous_2026=False)
    assert sim_300["annual_saved_kwh"] > 5000, f"Expected >5000 kWh/yr savings on 1987 300kVA, got {sim_300['annual_saved_kwh']}"
    logs.append(
        f"[OK] Verified JIS C 4304/4306 loss math (50-1000kVA): 1987 300kVA @45% load saves {sim_300['annual_saved_kwh']:,} kWh/yr ({sim_300['loss_reduction_pct']}%)."
    )

    # 5. 全47都道府県データと補助金・投資回収年数検証
    assert len(payload["subsidy_rules"]["prefectures"]) == 47, "Must include all 47 prefectures"
    sub_tokyo = calculate_subsidy_and_payback(
        equipment_yen=4_650_000,
        install_yen=1_650_000,
        compliance_extra_yen=995_000,
        annual_elec_saved_yen=225_000,
        annual_maint_saved_yen=185_000,
        prefecture_code="13",
        is_sme=True,
    )
    assert sub_tokyo["total_subsidy_yen"] > 2_000_000
    assert 1.0 <= sub_tokyo["payback_years"] <= 20.0
    logs.append(
        f"[OK] Verified 47-prefecture subsidy math: 300kVA Tokyo SME subsidy ¥{sub_tokyo['total_subsidy_yen']:,}, net payback {sub_tokyo['payback_years']} yrs."
    )

    # 6. 銘板OCRパーサー検証
    parsed_1 = parse_nameplate_text(SAMPLE_NAMEPLATES[0]["raw_text"])
    assert parsed_1["equipment_type"] == "cubicle"
    assert parsed_1["manufacturer_id"] == "mitsubishi"
    assert parsed_1["manufacturing_year"] == 1987
    assert parsed_1["capacity"] == 300

    parsed_old_alias = parse_nameplate_text("三相油入変圧器 150kVA 昭和46年製 東京芝浦電気株式会社")
    assert parsed_old_alias["manufacturer_id"] == "toshiba"
    assert parsed_old_alias["manufacturing_year"] == 1971
    assert parsed_old_alias["capacity"] == 150

    parsed_hvac = parse_nameplate_text(SAMPLE_NAMEPLATES[2]["raw_text"])
    assert parsed_hvac["equipment_type"] == "hvac"
    assert parsed_hvac["manufacturer_id"] == "daikin"
    assert parsed_hvac["manufacturing_year"] == 1999
    assert parsed_hvac["capacity"] == 20
    logs.append("[OK] Verified nameplate OCR text parser (Showa/Heisei/Western years, legacy corporate aliases, kVA/HP).")

    # 7. CTA設定ファイル整合性チェック
    for cta_path in (SITE_CTA_PATH, ROOT_CTA_PATH):
        if cta_path.exists():
            cta_data = json.loads(cta_path.read_text(encoding="utf-8"))
            assert cta_data.get("active_mode") in ("partner_form", "a8_affiliate", "rentracks_affiliate")
            assert "cubicle" in cta_data.get("channels", {}) and "hvac" in cta_data.get("channels", {})
    logs.append("[OK] Verified B2B CTA configuration JSON files.")

    return True, logs


def main() -> int:
    payload = build_rules_payload()
    ok, validation_logs = run_self_validation(payload)
    if not ok:
        print("Self-validation failed.", file=sys.stderr)
        return 1

    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Keep root data/cta_config.json and site/data/cta_config.json synchronized if one exists
    if SITE_CTA_PATH.exists() and not ROOT_CTA_PATH.exists():
        ROOT_CTA_PATH.parent.mkdir(parents=True, exist_ok=True)
        ROOT_CTA_PATH.write_text(SITE_CTA_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    for line in validation_logs:
        print(line)
    print(f"[SUCCESS] Generated {OUTPUT_JSON_PATH.relative_to(VENTURE_ROOT)} ({OUTPUT_JSON_PATH.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
