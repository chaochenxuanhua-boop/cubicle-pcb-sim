/*
 * Venture 03: 老朽キュービクル・業務用空調
 * 2027年PCB期限 × 2026アスベスト義務 × 省エネ補助金 一括判定シミュレーター
 * Frontend Simulation, Nameplate OCR Parser, SVG Cashflow Chart & Ringi-sho Generator
 */

(function () {
  "use strict";

  const HOURS_PER_YEAR = 8760;

  // file:// 直開き時でも動作する最小フォールバック定義（通常時は ./data/equipment_rules.json で上書き）
  const FALLBACK_RULES = {
    regulatory_deadlines: {
      pcb_low_conc_disposal_deadline: "2027-03-31",
      pcb_practical_sampling_deadline: "2026-10-31",
      pcb_penalty_summary:
        "改善命令違反時：3年以下の懲役若しくは1,000万円以下の罰金（又は併科）。2027年4月以降は環境省認定無害化処理施設での受入終了リスクあり。",
      asbestos_ban_threshold_year: 2006,
      asbestos_electronic_report_min_yen: 1000000,
      co2_emission_factor_kg_per_kwh: 0.438,
    },
    manufacturers: {
      mitsubishi: {
        id: "mitsubishi",
        name_ja: "三菱電機",
        supports_cubicle: true,
        supports_hvac: true,
        high_conc_pcb_end_year: 1972,
        low_conc_pcb_end_year: 1990,
        oil_refill_caution_end_year: 1994,
        pcb_window_detail_ja:
          "高濃度PCBは1972年以前製造分。低濃度PCB混入可能性は変圧器で1990年3月製造分までが確認対象です。",
        aliases: ["三菱電機", "三菱", "MITSUBISHI"],
      },
    },
    transformer_specs: {
      standard_capacities_kva: [50, 75, 100, 150, 200, 300, 500, 750, 1000],
      oil_jis_c_4304: {
        "300": {
          era_1970_1980: { no_load_w: 960, load_w: 4450 },
          era_1981_1990: { no_load_w: 780, load_w: 3850 },
          era_1991_2005: { no_load_w: 640, load_w: 3420 },
          era_2006_2013: { no_load_w: 430, load_w: 2980 },
          era_2014_2025: { no_load_w: 355, load_w: 2690 },
          target_2026_standard: { no_load_w: 285, load_w: 2360 },
          target_2026_amorphous: { no_load_w: 135, load_w: 2420 },
        },
      },
      mold_jis_c_4306: {
        "300": {
          era_1970_1980: { no_load_w: 1229, load_w: 5073 },
          era_1981_1990: { no_load_w: 998, load_w: 4389 },
          era_1991_2005: { no_load_w: 819, load_w: 3899 },
          era_2006_2013: { no_load_w: 550, load_w: 3397 },
          era_2014_2025: { no_load_w: 454, load_w: 3067 },
          target_2026_standard: { no_load_w: 365, load_w: 2690 },
          target_2026_amorphous: { no_load_w: 173, load_w: 2759 },
        },
      },
      capex_by_kva: {
        "300": {
          equipment_yen: 4650000,
          install_yen: 1650000,
          pcb_disposal_low_yen: 850000,
          pcb_disposal_high_yen: 2450000,
          asbestos_survey_yen: 145000,
          legacy_annual_maint_penalty_yen: 185000,
        },
      },
      era_labels: {
        era_1970_1980: "1970〜1980年製（初期JIS珪素鋼板世代）",
        era_1981_1990: "1981〜1990年製（旧JIS標準・低濃度PCB要確認世代）",
        era_1991_2005: "1991〜2005年製（トップランナー導入前世代）",
        era_2006_2013: "2006〜2013年製（第一次トップランナー基準世代）",
        era_2014_2025: "2014〜2025年製（第二次トップランナー基準世代）",
        target_2026_standard: "2026年度 第三次トップランナー基準適合変圧器",
        target_2026_amorphous: "2026年度 第三次トップランナー 超高効率アモルファス変圧器",
      },
    },
    hvac_specs: {
      standard_capacities_hp: [3, 5, 8, 10, 15, 20, 30, 40, 50],
      annual_full_load_equiv_hours_base: 2600,
      specs_by_hp: {
        "20": {
          cooling_kw: 56.0,
          apf_by_era: {
            era_1970_1994: 2.38,
            era_1995_2003: 2.95,
            era_2004_2010: 3.78,
            era_2011_2017: 4.32,
            era_2018_2025: 4.8,
            target_2026_top_runner: 5.35,
          },
          equipment_yen: 2680000,
          install_yen: 1080000,
          freon_recovery_yen: 160000,
          asbestos_survey_yen: 120000,
          legacy_annual_maint_penalty_yen: 155000,
        },
      },
      era_labels: {
        era_1970_1994: "1970〜1994年製（R22定速機・動力盤PCB注意世代）",
        era_1995_2003: "1995〜2003年製（R22/R407C旧インバータ世代）",
        era_2004_2010: "2004〜2010年製（R410A初期インバータ世代）",
        era_2011_2017: "2011〜2017年製（R410A中期インバータ世代）",
        era_2018_2025: "2018〜2025年製（R32現行インバータ世代）",
        target_2026_top_runner: "2026年最新 R32超高効率インバータ空調機",
      },
    },
    subsidy_rules: {
      national_sii: {
        program_name: "経済産業省（SII）省エネルギー投資促進支援事業（指定設備導入事業 1/3補助）",
        equipment_subsidy_rate: 0.333333,
        max_combined_subsidy_ratio: 0.66,
        tax_incentive_note: "中小企業経営強化税制（即時償却または10%税額控除）との比較検討推奨。",
      },
      prefectures: [
        {
          code: "13",
          name: "東京都",
          program_name: "クール・ネット東京 省エネ・非フロン機器導入助成",
          pref_addon_rate_sme: 0.22,
          pref_cap_yen: 5000000,
        },
      ],
    },
    sample_nameplates: [],
  };

  const FALLBACK_CTA = {
    active_mode: "partner_form",
    compliance: {
      tokushoho_required: false,
      operator_role: "無料技術試算ツールの提供および提携専門工事会社・公的相談窓口への送客（直接販売・決済なし）",
      show_pr_badge_in_affiliate_mode: true,
      pr_badge_text: "PR・提携専門業者ご案内",
    },
    channels: {
      cubicle: {
        headline: "【2027年3月PCB期限・SII省エネ補助金対応】高圧受変電キュービクル 無料現地調査・更新見積もり依頼",
        subheadline: "採油PCB分析・2026年工作物石綿事前調査・SII省エネ補助金申請サポートまで一括対応。",
        button_label: "診断結果を添付して無料現地調査・補助金対応見積もりを依頼する",
        partner_form_url: "mailto:chaochenxuanhua@gmail.com",
        a8_affiliate_url: "https://px.a8.net/svt/ejp?a8mat=3Z9CUB+PCB2027+4XYZ+60WN6",
        rentracks_affiliate_url: "https://www.rentracks.jp/adx/r.html?idx=0.58391.320419.7812.11204",
        append_diagnostic_params: true,
        trust_points: [
          "JEMA・環境省基準に基づく銘板確認＆絶縁油PCB微量分析（0.5mg/kg判定）手配対応",
          "2026年1月義務化の工作物石綿事前調査者によるガスケット・盤内調査込み",
        ],
        urgency_banner: "2026年秋以降は採油分析機関および無害化処理施設の受入枠逼迫が予測されます。",
      },
      hvac: {
        headline: "【R22フロン全廃・2026石綿調査・省エネ補助金対応】業務用パッケージ空調 一括更新見積もり",
        subheadline: "最新R32超高効率インバータ空調への更新と石綿事前調査・フロン回収証明書発行を一括手配。",
        button_label: "診断条件で業務用空調の省エネ補助金対応・無料現地見積もりを依頼する",
        partner_form_url: "mailto:chaochenxuanhua@gmail.com",
        a8_affiliate_url: "https://px.a8.net/svt/ejp?a8mat=3Z9HVC+AIR2026+5ABC+61Z82",
        rentracks_affiliate_url: "https://www.rentracks.jp/adx/r.html?idx=0.58391.320420.8901.13420",
        append_diagnostic_params: true,
        trust_points: ["第一種フロン類充填回収業者による適法回収証明書発行", "SII指定設備1/3補助・自治体助成対応"],
        urgency_banner: "R22冷媒機は部品枯渇により突発停止時の長期操業停止リスクがあります。",
      },
    },
    public_reference_links: [],
  };

  let RULES = FALLBACK_RULES;
  let CTA_CONFIG = FALLBACK_CTA;
  let lastResult = null;

  function formatYen(val) {
    return "¥" + Math.round(val).toLocaleString("ja-JP");
  }

  function formatManYen(val) {
    const man = Math.round(val / 10000);
    return man.toLocaleString("ja-JP") + "万円";
  }

  function formatNum(val) {
    return Math.round(val).toLocaleString("ja-JP");
  }

  function toWarekiLabel(year) {
    const currentYear = new Date().getFullYear();
    const age = Math.max(0, currentYear - year);
    let era = "";
    if (year <= 1988) {
      era = "昭和" + (year - 1925) + "年";
    } else if (year === 1989) {
      era = "平成元年 / 昭和64年";
    } else if (year <= 2018) {
      era = "平成" + (year - 1988) + "年";
    } else if (year === 2019) {
      era = "令和元年";
    } else {
      era = "令和" + (year - 2018) + "年";
    }
    return era + " ／ 経年" + age + "年";
  }

  function calcDaysUntil(isoDateStr) {
    const now = new Date();
    const todayUtc = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
    const parts = isoDateStr.split("-").map(Number);
    const targetUtc = Date.UTC(parts[0], parts[1] - 1, parts[2]);
    return Math.ceil((targetUtc - todayUtc) / (1000 * 60 * 60 * 24));
  }

  function updateCountdownHeader() {
    const pcbDays = calcDaysUntil(RULES.regulatory_deadlines.pcb_low_conc_disposal_deadline);
    const labDays = calcDaysUntil(RULES.regulatory_deadlines.pcb_practical_sampling_deadline);

    const pcbEl = document.getElementById("pcb-days-remaining");
    const labEl = document.getElementById("pcb-lab-days-remaining");
    const chipEl = document.getElementById("pcb-remaining-chip");

    const pcbText = pcbDays > 0 ? String(pcbDays) : "期限超過";
    if (pcbEl) pcbEl.textContent = pcbText;
    if (labEl) labEl.textContent = labDays > 0 ? String(labDays) : "期限到来・即時手配要";
    if (chipEl) {
      chipEl.textContent = pcbDays > 0 ? "2027/3/31まで残り " + pcbDays + " 日" : "法定処分期限 到来済";
    }

    const now = new Date();
    const printDateEl = document.getElementById("print-date-str");
    if (printDateEl) {
      printDateEl.textContent =
        now.getFullYear() + "年" + (now.getMonth() + 1) + "月" + now.getDate() + "日";
    }
  }

  function populateManufacturers(equipType, keepValue) {
    const select = document.getElementById("manufacturer-select");
    const makers = Object.values(RULES.manufacturers);
    const prev = keepValue || select.value;
    select.innerHTML = "";

    const primaryGroup = document.createElement("optgroup");
    primaryGroup.label =
      equipType === "cubicle" ? "主要 受変電・変圧器メーカー" : "主要 業務用空調メーカー";
    const secondaryGroup = document.createElement("optgroup");
    secondaryGroup.label = "その他メーカー・盤OEM";

    makers.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      const windowNote =
        equipType === "cubicle" && m.id !== "daikin"
          ? "（低濃度PCB確認: 〜" + m.low_conc_pcb_end_year + "年）"
          : "";
      opt.textContent = m.name_ja + windowNote;
      const isPrimary = equipType === "cubicle" ? m.supports_cubicle : m.supports_hvac;
      if (isPrimary) {
        primaryGroup.appendChild(opt);
      } else {
        secondaryGroup.appendChild(opt);
      }
    });

    select.appendChild(primaryGroup);
    if (secondaryGroup.children.length > 0) {
      select.appendChild(secondaryGroup);
    }

    const allIds = makers.map((m) => m.id);
    if (prev && allIds.includes(prev)) {
      select.value = prev;
    } else {
      select.value = equipType === "cubicle" ? "mitsubishi" : "daikin";
    }
  }

  function populateCapacities(equipType, targetVal) {
    const select = document.getElementById("capacity-select");
    const label = document.getElementById("capacity-label");
    select.innerHTML = "";

    if (equipType === "cubicle") {
      label.textContent = "定格容量 (kVA)";
      const list = RULES.transformer_specs.standard_capacities_kva;
      list.forEach((kva) => {
        const opt = document.createElement("option");
        opt.value = String(kva);
        opt.textContent = kva + " kVA（三相 6.6kV級）";
        select.appendChild(opt);
      });
      const nearest = findNearestKey(list, targetVal || 300);
      select.value = String(nearest);
    } else {
      label.textContent = "空調能力 (馬力 / kW)";
      const list = RULES.hvac_specs.standard_capacities_hp;
      list.forEach((hp) => {
        const spec = RULES.hvac_specs.specs_by_hp[String(hp)];
        const kwText = spec ? " / 冷房" + spec.cooling_kw + "kW" : "";
        const opt = document.createElement("option");
        opt.value = String(hp);
        opt.textContent = hp + " 馬力" + kwText;
        select.appendChild(opt);
      });
      const nearest = findNearestKey(list, targetVal || 20);
      select.value = String(nearest);
    }
  }

  function populatePrefectures() {
    const select = document.getElementById("prefecture-select");
    select.innerHTML = "";
    RULES.subsidy_rules.prefectures.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.code;
      opt.textContent = p.name + "（自治体加算上限 " + Math.round(p.pref_cap_yen / 10000) + "万円）";
      select.appendChild(opt);
    });
    select.value = "13";
  }

  function populateSampleButtons() {
    const wrap = document.getElementById("sample-buttons-container");
    wrap.innerHTML = "";
    (RULES.sample_nameplates || []).forEach((sample) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "sample-chip-btn";
      btn.textContent = sample.label;
      btn.addEventListener("click", () => {
        const area = document.getElementById("nameplate-input");
        area.value = sample.raw_text;
        applyNameplateParse(sample.raw_text);
      });
      wrap.appendChild(btn);
    });
  }

  function populateReferenceLinks() {
    const wrap = document.getElementById("public-ref-links");
    wrap.innerHTML = "";
    (CTA_CONFIG.public_reference_links || []).forEach((item) => {
      const a = document.createElement("a");
      a.href = item.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = item.title;
      wrap.appendChild(a);
    });
  }

  function findNearestKey(numArray, target) {
    return numArray.reduce((prev, curr) =>
      Math.abs(curr - target) < Math.abs(prev - target) ? curr : prev
    );
  }

  // 銘板テキスト自動パーサー（NFKC正規化・和暦変換・旧社名変換・R22誤認防止ガード付）
  function parseNameplateText(rawText) {
    const normalized = rawText.normalize("NFKC");
    const upper = normalized.toUpperCase();
    const reasons = [];

    const hvacKeywords = ["エアコン", "パッケージ", "室外", "冷媒", "R22", "R410A", "R32", "ヒートポンプ", "馬力", "空冷"];
    const cubicleStrict = ["変圧器", "キュービクル", "6600V", "6.6KV", "絶縁油"];
    const isHvac =
      hvacKeywords.some((k) => upper.includes(k)) && !cubicleStrict.some((k) => upper.includes(k));
    const equipmentType = isHvac ? "hvac" : "cubicle";
    reasons.push(
      "設備種別判定: " + (equipmentType === "hvac" ? "業務用パッケージ空調" : "高圧受変電キュービクル・変圧器")
    );

    let detectedMaker = null;
    for (const [makerId, mdata] of Object.entries(RULES.manufacturers)) {
      if (makerId === "other") continue;
      for (const alias of mdata.aliases || []) {
        if (upper.includes(alias.toUpperCase())) {
          detectedMaker = makerId;
          reasons.push("メーカー特定: 「" + alias + "」 → " + mdata.name_ja);
          break;
        }
      }
      if (detectedMaker) break;
    }

    let detectedYear = null;
    const mShowa =
      upper.match(/昭和\s*(\d{1,2})\s*年?/) || upper.match(/(?<![A-Z0-9-])S\s*(\d{2})(?:\s*年|\.\d{1,2})/);
    const mHeisei =
      upper.match(/平成\s*(\d{1,2}|元)\s*年?/) || upper.match(/(?<![A-Z0-9-])H\s*(\d{1,2})(?:\s*年|\.\d{1,2})/);
    const mReiwa =
      upper.match(/令和\s*(\d{1,2}|元)\s*年?/) || upper.match(/(?<![A-Z0-9-])R\s*([1-9])(?:\s*年|\.\d{1,2})/);
    const mWest =
      normalized.match(/(19[6-9]\d|20[0-2]\d)\s*年/) || normalized.match(/\b(19[6-9]\d|20[0-2]\d)\b/);

    if (mShowa) {
      const n = parseInt(mShowa[1], 10);
      detectedYear = 1925 + n;
      reasons.push("和暦変換: 昭和" + n + "年 → 西暦" + detectedYear + "年");
    } else if (mHeisei) {
      const n = mHeisei[1] === "元" ? 1 : parseInt(mHeisei[1], 10);
      detectedYear = 1988 + n;
      reasons.push("和暦変換: 平成" + mHeisei[1] + "年 → 西暦" + detectedYear + "年");
    } else if (mReiwa) {
      const n = mReiwa[1] === "元" ? 1 : parseInt(mReiwa[1], 10);
      detectedYear = 2018 + n;
      reasons.push("和暦変換: 令和" + mReiwa[1] + "年 → 西暦" + detectedYear + "年");
    } else if (mWest) {
      detectedYear = parseInt(mWest[1], 10);
      reasons.push("製造年抽出: 西暦" + detectedYear + "年");
    }

    if (detectedYear !== null) {
      detectedYear = Math.max(1970, Math.min(2025, detectedYear));
    }

    let detectedCapacity = null;
    if (equipmentType === "cubicle") {
      const mKva = upper.match(/(\d{2,4})\s*KVA/);
      if (mKva) {
        detectedCapacity = parseInt(mKva[1], 10);
        reasons.push("定格容量抽出: " + detectedCapacity + " kVA");
      }
    } else {
      const mHp = upper.match(/(\d{1,3})\s*(?:馬力|HP)/);
      const mKw = upper.match(/(\d{1,3}(?:\.\d+)?)\s*KW/);
      if (mHp) {
        detectedCapacity = parseInt(mHp[1], 10);
        reasons.push("空調馬力抽出: " + detectedCapacity + " 馬力");
      } else if (mKw) {
        const kw = parseFloat(mKw[1]);
        detectedCapacity = Math.max(3, Math.round(kw / 2.8));
        reasons.push("冷房能力換算: " + kw + " kW → 約" + detectedCapacity + " 馬力相当");
      }
    }

    const insulationType =
      normalized.includes("モールド") || normalized.includes("乾式") || upper.includes("JIS C 4306")
        ? "mold"
        : "oil";
    if (equipmentType === "cubicle") {
      reasons.push("絶縁冷却方式: " + (insulationType === "mold" ? "モールド変圧器（乾式）" : "油入変圧器"));
    }

    return {
      equipmentType,
      detectedMaker,
      detectedYear,
      detectedCapacity,
      insulationType,
      reasons,
    };
  }

  function applyNameplateParse(rawText) {
    const feedbackEl = document.getElementById("ocr-parse-feedback");
    if (!rawText || !rawText.trim()) {
      feedbackEl.classList.remove("hidden");
      feedbackEl.innerHTML = "<strong>銘板テキストが未入力です。</strong>サンプルボタンを押すかテキストを貼り付けてください。";
      return;
    }

    const parsed = parseNameplateText(rawText);
    setEquipmentType(parsed.equipmentType, parsed.detectedMaker, parsed.detectedCapacity);

    if (parsed.detectedMaker) {
      document.getElementById("manufacturer-select").value = parsed.detectedMaker;
    }
    if (parsed.detectedYear) {
      document.getElementById("manufacturing-year").value = String(parsed.detectedYear);
      document.getElementById("manufacturing-year-range").value = String(Math.min(2020, parsed.detectedYear));
    }
    if (parsed.equipmentType === "cubicle") {
      document.getElementById("insulation-type").value = parsed.insulationType;
    }

    feedbackEl.classList.remove("hidden");
    feedbackEl.innerHTML =
      "<strong>銘板自動読取完了（フォームへ反映済）：</strong><ul>" +
      parsed.reasons.map((r) => "<li>" + escapeHtml(r) + "</li>").join("") +
      "</ul>";

    runDiagnostic();
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function classifyTransformerEra(year) {
    if (year <= 1980) return "era_1970_1980";
    if (year <= 1990) return "era_1981_1990";
    if (year <= 2005) return "era_1991_2005";
    if (year <= 2013) return "era_2006_2013";
    return "era_2014_2025";
  }

  function classifyHvacEra(year) {
    if (year <= 1994) return "era_1970_1994";
    if (year <= 2003) return "era_1995_2003";
    if (year <= 2010) return "era_2004_2010";
    if (year <= 2017) return "era_2011_2017";
    return "era_2018_2025";
  }

  function evaluatePcbRisk(equipType, makerId, year, insulationType) {
    const maker = RULES.manufacturers[makerId] || RULES.manufacturers.other || Object.values(RULES.manufacturers)[0];
    const highEnd = maker.high_conc_pcb_end_year;
    const lowEnd = maker.low_conc_pcb_end_year;
    const refillEnd = maker.oil_refill_caution_end_year;

    if (equipType === "hvac") {
      if (year <= highEnd) {
        return {
          severity: "critical",
          code: "HIGH_CONC_AUX_CAPACITOR_RISK",
          badge: "【最重大】高濃度PCBコンデンサ混在リスク＋R22冷媒全廃機",
          analysisRequired: true,
          disposalTier: "high",
          summary:
            year +
            "年製の大型空調設備は付属動力盤内の力率改善コンデンサに高濃度PCBが含まれる可能性があり、直ちに銘板確認と電気主任技術者への相談が必要です。",
        };
      }
      if (year <= lowEnd) {
        return {
          severity: "high",
          code: "LOW_CONC_AUX_CAPACITOR_AND_R22",
          badge: "【2027年3月期限】動力盤コンデンサ低濃度PCB確認＋R22全廃機",
          analysisRequired: true,
          disposalTier: "low",
          summary:
            year +
            "年製のため、付属動力盤内の油入コンデンサが2027年3月31日低濃度PCB処分期限の対象か確認が必要です。冷媒R22も生産終了しています。",
        };
      }
      if (year <= 2003) {
        return {
          severity: "medium",
          code: "R22_FREON_PHASEOUT_RISK",
          badge: "PCB原則対象外 ／ 【注意】R22旧フロン生産終了・部品枯渇世代",
          analysisRequired: false,
          disposalTier: "none",
          summary:
            "空調機本体のPCBリスクは低いですが、R22(HCFC)冷媒の全廃により圧縮機故障・ガス漏洩時の修理不能リスクが極めて高い更新優先世代です。",
        };
      }
      return {
        severity: "low",
        code: "PCB_CLEAR_HVAC",
        badge: "PCB規制対象外（フロン排出抑制法の定期点検・回収証明対象）",
        analysisRequired: false,
        disposalTier: "none",
        summary:
          "1995年以降製造のためPCB規制対象外です。更新撤去時は第一種フロン類充填回収業者によるフロン回収と行程管理票の保存を行ってください。",
      };
    }

    if (insulationType === "mold" && year > highEnd) {
      return {
        severity: "low",
        code: "MOLD_DRY_TYPE_CLEAR",
        badge: "乾式（モールド変圧器）のため絶縁油PCB対象外（※盤内コンデンサのみ確認）",
        analysisRequired: false,
        disposalTier: "none",
        summary:
          "モールド変圧器本体は絶縁油を使用しないためPCB汚染対象外です。ただしキュービクル内の高圧進相コンデンサ(SC)が1990年以前製でないか銘板確認を推奨します。",
      };
    }

    if (year <= highEnd) {
      return {
        severity: "critical",
        code: "HIGH_CONC_PCB_EXPIRED",
        badge: "【緊急法令対応】高濃度PCB該当リスク（法定処分期限経過済）",
        analysisRequired: true,
        disposalTier: "high",
        summary:
          maker.name_ja +
          "の" +
          year +
          "年製機器は1972年以前製造の高濃度PCB使用電気工作物に該当する可能性が高く、電気主任技術者および自治体環境部局への即時届出・確認が必要です。",
      };
    }

    if (year <= lowEnd) {
      return {
        severity: "high",
        code: "LOW_CONC_PCB_2027_DEADLINE",
        badge: "【2027年3月31日処分期限】低濃度PCB混入可能性あり（" + maker.name_ja + "：〜" + lowEnd + "年）",
        analysisRequired: true,
        disposalTier: "low",
        summary:
          maker.pcb_window_detail_ja +
          " 採油によるPCB濃度分析（0.5mg/kg超で該当）および2027年3月31日までの無害化処理完了が法定義務です。",
      };
    }

    if (year <= refillEnd) {
      return {
        severity: "medium",
        code: "OIL_REFILL_HISTORY_CHECK",
        badge: "【準注意】出荷時PCB不含世代 ／ " + refillEnd + "年以前の絶縁油補油歴のみ要確認",
        analysisRequired: true,
        disposalTier: "sampling_only",
        summary:
          maker.name_ja +
          "の出荷時混入期間（〜" +
          lowEnd +
          "年）以降ですが、" +
          refillEnd +
          "年以前に再生絶縁油の補油・交換履歴がある場合は廃棄時の採油分析が必要です。",
      };
    }

    return {
      severity: "low",
      code: "PCB_CLEAR_POST_1995",
      badge: "PCB規制対象外（1995年以降の非PCB確定世代）",
      analysisRequired: false,
      disposalTier: "none",
      summary: year + "年製造のためPCB混入リスクは原則ありません。通常の産業廃棄物処理フローで適法に更新可能です。",
    };
  }

  function evaluateAsbestos(year, grossCapexYen) {
    const banYear = RULES.regulatory_deadlines.asbestos_ban_threshold_year || 2006;
    const minReportYen = RULES.regulatory_deadlines.asbestos_electronic_report_min_yen || 1000000;
    const needElectronic = grossCapexYen >= minReportYen;

    if (year <= banYear) {
      return {
        severity: "high",
        physicalSurveyRequired: true,
        electronicReportRequired: needElectronic,
        badge: "【2026年1月完全義務化】工作物石綿事前調査者による現地・分析調査 必須",
        chipText: needElectronic ? "有資格調査＋GビズID電子報告義務" : "有資格者事前調査 必須",
        summary:
          year +
          "年製（2006年8月以前の石綿全面禁止前）のため、2026年1月施行の改正大気汚染防止法・石綿則により、更新・撤去工事前に「工作物石綿事前調査者」等の有資格者によるガスケット・断熱材・耐火パテ・塗膜の事前調査が義務化されています。" +
          (needElectronic ? "請負金額100万円以上のためGビズIDでの労基署・自治体電子報告も必須です。" : ""),
      };
    }

    return {
      severity: "low",
      physicalSurveyRequired: false,
      electronicReportRequired: needElectronic,
      badge: "書面事前調査（2006年9月以降着工の銘板・設計図書確認）で対応可",
      chipText: needElectronic ? "書面記録保存＋GビズID電子報告" : "書面調査記録3年保存",
      summary:
        year +
        "年製（石綿全面禁止以降）のため検体採取分析は不要ですが、製造年銘板・竣工図による書面事前調査記録の作成・3年間保存" +
        (needElectronic ? "および請負金額100万円以上のGビズID電子報告" : "") +
        "は法定手続きとして必須です。",
    };
  }

  function runDiagnostic() {
    const equipType = document.getElementById("equipment-type").value;
    const makerId = document.getElementById("manufacturer-select").value;
    const year = Math.max(1970, Math.min(2025, parseInt(document.getElementById("manufacturing-year").value, 10) || 1987));
    const capacity = parseInt(document.getElementById("capacity-select").value, 10) || (equipType === "cubicle" ? 300 : 20);
    const unitCount = Math.max(1, Math.min(20, parseInt(document.getElementById("unit-count").value, 10) || 1));
    const loadFactor = Math.max(10, Math.min(100, parseFloat(document.getElementById("load-factor").value) || 45));
    const elecRate = Math.max(10, Math.min(80, parseFloat(document.getElementById("elec-rate").value) || 27.0));
    const prefCode = document.getElementById("prefecture-select").value || "13";
    const isSme = document.getElementById("sme-status").value === "sme";
    const insulationType = document.getElementById("insulation-type").value || "oil";
    const upgradeSpec = document.getElementById("upgrade-spec").value || "amorphous";

    document.getElementById("wareki-helper").textContent = toWarekiLabel(year);

    const makerObj = RULES.manufacturers[makerId] || Object.values(RULES.manufacturers)[0];
    const prefObj =
      RULES.subsidy_rules.prefectures.find((p) => p.code === prefCode) || RULES.subsidy_rules.prefectures[0];

    const pcbEval = evaluatePcbRisk(equipType, makerId, year, insulationType);

    let specRows = [];
    let formulaText = "";
    let legacyAnnualKwh = 0;
    let modernAnnualKwh = 0;
    let equipmentYen = 0;
    let installYen = 0;
    let complianceExtraYen = 0;
    let complianceBreakdownLabel = "";
    let legacyMaintPenaltyYen = 0;
    let pcbDeferredPenaltyYen = 0;

    if (equipType === "cubicle") {
      const lossTable =
        insulationType === "mold"
          ? RULES.transformer_specs.mold_jis_c_4306
          : RULES.transformer_specs.oil_jis_c_4304;
      const kvaKey = String(findNearestKey(Object.keys(lossTable).map(Number), capacity));
      const eraKey = classifyTransformerEra(year);
      const targetKey = upgradeSpec === "amorphous" ? "target_2026_amorphous" : "target_2026_standard";

      const legacySpec = lossTable[kvaKey][eraKey];
      const modernSpec = lossTable[kvaKey][targetKey];
      const mRatio = loadFactor / 100.0;

      const legacyLoadLossAtM = Math.round(mRatio * mRatio * legacySpec.load_w);
      const modernLoadLossAtM = Math.round(mRatio * mRatio * modernSpec.load_w);
      const legacyTotalW = legacySpec.no_load_w + legacyLoadLossAtM;
      const modernTotalW = modernSpec.no_load_w + modernLoadLossAtM;

      legacyAnnualKwh = Math.round((legacyTotalW / 1000.0) * HOURS_PER_YEAR) * unitCount;
      modernAnnualKwh = Math.round((modernTotalW / 1000.0) * HOURS_PER_YEAR) * unitCount;

      const capexBase =
        RULES.transformer_specs.capex_by_kva[kvaKey] || Object.values(RULES.transformer_specs.capex_by_kva)[0];
      const amorphousMultiplier = upgradeSpec === "amorphous" ? 1.12 : 1.0;
      equipmentYen = Math.round(capexBase.equipment_yen * amorphousMultiplier) * unitCount;
      installYen = capexBase.install_yen * unitCount;

      let pcbCost = 0;
      if (pcbEval.disposalTier === "high") {
        pcbCost = capexBase.pcb_disposal_high_yen * unitCount;
        pcbDeferredPenaltyYen = Math.round(pcbCost * 1.35);
      } else if (pcbEval.disposalTier === "low") {
        pcbCost = capexBase.pcb_disposal_low_yen * unitCount;
        pcbDeferredPenaltyYen = Math.round(pcbCost * 1.25);
      } else if (pcbEval.disposalTier === "sampling_only") {
        pcbCost = 55000 * unitCount;
      }

      const asbCost = year <= 2006 ? capexBase.asbestos_survey_yen * unitCount : 25000 * unitCount;
      complianceExtraYen = pcbCost + asbCost;
      complianceBreakdownLabel =
        (pcbCost > 0 ? "PCB分析・無害化処理費 " + formatYen(pcbCost) + " ＋ " : "") +
        "石綿事前調査・法定手続費 " +
        formatYen(asbCost);

      const ageFactor = year <= 1990 ? 1.25 : year <= 2005 ? 1.0 : 0.55;
      legacyMaintPenaltyYen = Math.round(capexBase.legacy_annual_maint_penalty_yen * ageFactor) * unitCount;

      specRows = [
        ["適用規格・世代区分", RULES.transformer_specs.era_labels[eraKey], RULES.transformer_specs.era_labels[targetKey]],
        ["定格容量 × 台数", kvaKey + " kVA × " + unitCount + "台", kvaKey + " kVA × " + unitCount + "台"],
        ["無負荷損（鉄損 W0 / 1台）", legacySpec.no_load_w + " W（24h常時発生）", modernSpec.no_load_w + " W"],
        ["定格負荷損（銅損 Wc / 1台）", legacySpec.load_w + " W", modernSpec.load_w + " W"],
        ["実効負荷率 " + loadFactor + "%時の総損失/台", legacyTotalW + " W", modernTotalW + " W"],
        ["年間損失電力量（" + unitCount + "台計）", formatNum(legacyAnnualKwh) + " kWh/年", formatNum(modernAnnualKwh) + " kWh/年"],
        [
          "年間電力ロス金額（@" + elecRate + "円）",
          formatYen(legacyAnnualKwh * elecRate) + "/年",
          formatYen(modernAnnualKwh * elecRate) + "/年",
        ],
      ];
      formulaText =
        "計算式（JIS C 4304/4306）：年間損失電力量 [kWh] ＝ { 無負荷損 W0 ＋ (実効負荷率 " +
        loadFactor +
        "% ÷ 100)² × 定格負荷損 Wc } ÷ 1000 × 8,760時間 × " +
        unitCount +
        "台";
      document.getElementById("spec-comparison-title").textContent =
        "JIS C 4304/4306 変圧器損失（無負荷損＋負荷損）比較根拠";
    } else {
      const hpKey = String(findNearestKey(Object.keys(RULES.hvac_specs.specs_by_hp).map(Number), capacity));
      const hSpec = RULES.hvac_specs.specs_by_hp[hpKey] || Object.values(RULES.hvac_specs.specs_by_hp)[0];
      const eraKey = classifyHvacEra(year);
      const legacyApf = hSpec.apf_by_era[eraKey];
      const modernApf = hSpec.apf_by_era.target_2026_top_runner;
      const baseHours = RULES.hvac_specs.annual_full_load_equiv_hours_base || 2600;
      const annualThermalKwh = hSpec.cooling_kw * (loadFactor / 100.0) * baseHours;

      legacyAnnualKwh = Math.round(annualThermalKwh / legacyApf) * unitCount;
      modernAnnualKwh = Math.round(annualThermalKwh / modernApf) * unitCount;

      equipmentYen = hSpec.equipment_yen * unitCount;
      installYen = hSpec.install_yen * unitCount;
      const freonCost = hSpec.freon_recovery_yen * unitCount;
      const asbCost = year <= 2006 ? hSpec.asbestos_survey_yen * unitCount : 20000 * unitCount;
      complianceExtraYen = freonCost + asbCost;
      complianceBreakdownLabel =
        "第一種フロン回収・破壊処理費 " + formatYen(freonCost) + " ＋ 石綿事前調査費 " + formatYen(asbCost);

      const ageFactor = year <= 2003 ? 1.3 : year <= 2012 ? 0.9 : 0.5;
      legacyMaintPenaltyYen = Math.round(hSpec.legacy_annual_maint_penalty_yen * ageFactor) * unitCount;
      pcbDeferredPenaltyYen = year <= 1990 ? 180000 * unitCount : 0;

      specRows = [
        ["世代・冷媒区分", RULES.hvac_specs.era_labels[eraKey], RULES.hvac_specs.era_labels.target_2026_top_runner],
        ["空調能力 × 系統数", hpKey + "馬力（" + hSpec.cooling_kw + "kW）× " + unitCount + "系統", hpKey + "馬力 × " + unitCount + "系統"],
        ["通年エネルギー消費効率 (APF)", legacyApf.toFixed(2), modernApf.toFixed(2) + "（省エネ基準達成）"],
        ["年間消費電力量（負荷率" + loadFactor + "%）", formatNum(legacyAnnualKwh) + " kWh/年", formatNum(modernAnnualKwh) + " kWh/年"],
        [
          "年間空調電気料金（@" + elecRate + "円）",
          formatYen(legacyAnnualKwh * elecRate) + "/年",
          formatYen(modernAnnualKwh * elecRate) + "/年",
        ],
      ];
      formulaText =
        "計算式：年間消費電力量 [kWh] ＝ 定格能力 " +
        hSpec.cooling_kw +
        "kW × 負荷率 " +
        loadFactor +
        "% × 年間換算稼働 " +
        baseHours +
        "h ÷ APF × " +
        unitCount +
        "系統";
      document.getElementById("spec-comparison-title").textContent =
        "業務用パッケージ空調 APF（通年エネルギー消費効率）・消費電力比較根拠";
    }

    const grossCapex = equipmentYen + installYen + complianceExtraYen;
    const asbestosEval = evaluateAsbestos(year, grossCapex);

    const annualSavedKwh = Math.max(0, legacyAnnualKwh - modernAnnualKwh);
    const annualElecSavedYen = Math.round(annualSavedKwh * elecRate);
    const annualTotalBenefitYen = annualElecSavedYen + legacyMaintPenaltyYen;
    const co2SavedTons = ((annualSavedKwh * RULES.regulatory_deadlines.co2_emission_factor_kg_per_kwh) / 1000.0).toFixed(2);

    // 補助金計算：経産省SII 1/3補助（設備費ベース）＋ 都道府県中小企業加算
    const siiSubsidyYen = Math.round(equipmentYen / 3.0);
    const prefAddonYen = isSme
      ? Math.min(Math.round((equipmentYen + installYen) * prefObj.pref_addon_rate_sme), prefObj.pref_cap_yen)
      : 0;
    const totalSubsidyYen = Math.min(siiSubsidyYen + prefAddonYen, Math.round(grossCapex * 0.66));
    const netCapexYen = Math.max(0, grossCapex - totalSubsidyYen);
    const paybackYears = annualTotalBenefitYen > 0 ? netCapexYen / annualTotalBenefitYen : 99.9;

    // 10年間累積差額キャッシュアウト配列（Year 0..10）
    // 放置シナリオ: Year 0 = 0円、毎年 (年間電気代ロス差額 + 老朽保安・突発修理リスク費) が累積、PCB期限対象機はYear 1に無補助法定処分・緊急対応コスト加算
    // 補助金更新シナリオ: Year 0 = 実質自己負担額 (netCapexYen)、以降は毎年の過剰ロス0円
    const legacySeries = [];
    const upgradeSeries = [];
    for (let yr = 0; yr <= 10; yr++) {
      const pcbPenaltyAtYr = yr >= 1 ? pcbDeferredPenaltyYen : 0;
      legacySeries.push(yr * annualTotalBenefitYen + pcbPenaltyAtYr);
      upgradeSeries.push(netCapexYen);
    }
    const tenYearNetAdvantage = legacySeries[10] - upgradeSeries[10];

    lastResult = {
      equipType,
      makerName: makerObj.name_ja,
      makerId,
      year,
      capacity,
      unitCount,
      loadFactor,
      elecRate,
      prefName: prefObj.name,
      prefProgram: prefObj.program_name,
      prefCode,
      isSme,
      insulationType,
      upgradeSpec,
      pcbEval,
      asbestosEval,
      annualSavedKwh,
      annualElecSavedYen,
      legacyMaintPenaltyYen,
      annualTotalBenefitYen,
      co2SavedTons,
      equipmentYen,
      installYen,
      complianceExtraYen,
      complianceBreakdownLabel,
      grossCapex,
      siiSubsidyYen,
      prefAddonYen,
      totalSubsidyYen,
      netCapexYen,
      paybackYears,
      tenYearNetAdvantage,
      legacySeries,
      upgradeSeries,
    };

    renderDashboard(lastResult, specRows, formulaText);
  }

  function renderDashboard(res, specRows, formulaText) {
    const unitLabel = res.equipType === "cubicle" ? res.capacity + "kVA" : res.capacity + "馬力";
    const equipShort = res.equipType === "cubicle" ? "高圧受変電・変圧器" : "業務用パッケージ空調";
    const titleStr =
      res.makerName +
      " " +
      res.year +
      "年製 " +
      unitLabel +
      "×" +
      res.unitCount +
      "（" +
      res.prefName +
      "・" +
      (res.isSme ? "中小企業" : "大企業") +
      "）の診断結果";
    document.getElementById("active-sim-title").textContent = titleStr;

    // 印刷用ヘッダー更新
    const facName = document.getElementById("facility-name-input").value || "対象事業場";
    const deptName = document.getElementById("dept-name-input").value || "施設管理担当";
    document.getElementById("print-facility-name").textContent = facName;
    document.getElementById("print-dept-name").textContent = deptName;
    document.getElementById("print-condition-bar").innerHTML =
      "<strong>【試算前提条件】</strong> 対象設備：" +
      escapeHtml(equipShort) +
      " ／ メーカー：" +
      escapeHtml(res.makerName) +
      " ／ 製造年：" +
      res.year +
      "年（" +
      escapeHtml(toWarekiLabel(res.year)) +
      "） ／ 定格容量：" +
      unitLabel +
      " × " +
      res.unitCount +
      " ／ 平均負荷率：" +
      res.loadFactor +
      "% ／ 電力単価：" +
      res.elecRate +
      "円/kWh ／ 所在地：" +
      escapeHtml(res.prefName) +
      "（" +
      (res.isSme ? "中小企業区分" : "大企業区分") +
      "）";

    // PCBカード更新
    const cardPcb = document.getElementById("card-pcb");
    cardPcb.className = "status-card severity-" + res.pcbEval.severity;
    document.getElementById("pcb-badge-title").textContent = res.pcbEval.badge;
    document.getElementById("pcb-summary-text").textContent = res.pcbEval.summary;
    document.getElementById("pcb-penalty-note").textContent =
      "法令根拠：" + RULES.regulatory_deadlines.pcb_penalty_summary;

    // アスベストカード更新
    const cardAsb = document.getElementById("card-asbestos");
    cardAsb.className = "status-card severity-" + res.asbestosEval.severity;
    document.getElementById("asbestos-badge-title").textContent = res.asbestosEval.badge;
    document.getElementById("asbestos-summary-text").textContent = res.asbestosEval.summary;
    document.getElementById("asbestos-report-chip").textContent = res.asbestosEval.chipText;

    // KPI 4連更新
    document.getElementById("kpi-annual-saving").textContent = formatYen(res.annualTotalBenefitYen) + "/年";
    document.getElementById("kpi-kwh-saving").textContent =
      "電気代削減 " +
      formatYen(res.annualElecSavedYen) +
      "（-" +
      formatNum(res.annualSavedKwh) +
      " kWh ／ CO2 -" +
      res.co2SavedTons +
      " t/年）";

    document.getElementById("kpi-total-subsidy").textContent = formatYen(res.totalSubsidyYen);
    document.getElementById("kpi-subsidy-breakdown").textContent =
      "国庫SII " +
      formatManYen(res.siiSubsidyYen) +
      (res.prefAddonYen > 0 ? " ＋ " + res.prefName + "加算 " + formatManYen(res.prefAddonYen) : "（大企業1/3枠）");

    document.getElementById("kpi-net-capex").textContent = formatYen(res.netCapexYen);
    document.getElementById("kpi-gross-capex").textContent = "総事業費目安 " + formatYen(res.grossCapex);

    document.getElementById("kpi-payback-years").textContent = res.paybackYears.toFixed(1) + " 年";
    const advSign = res.tenYearNetAdvantage >= 0 ? "+" : "";
    document.getElementById("kpi-10yr-net-advantage").textContent =
      "放置比10年累計純効果 " + advSign + formatManYen(res.tenYearNetAdvantage);

    // 技術仕様テーブル描画
    const specTbody = document.getElementById("spec-comparison-tbody");
    specTbody.innerHTML = specRows
      .map(
        (r) =>
          "<tr><td>" +
          escapeHtml(r[0]) +
          "</td><td class='num'>" +
          escapeHtml(r[1]) +
          "</td><td class='num'>" +
          escapeHtml(r[2]) +
          "</td></tr>"
      )
      .join("");
    document.getElementById("formula-footnote").textContent = formulaText;

    // 事業費・補助金内訳テーブル描画
    const finRows = [
      ["① 2026高効率機器 本体設備費（補助対象）", formatYen(res.equipmentYen), ""],
      ["② 更新据付・停電切替・試運転工事費", formatYen(res.installYen), ""],
      ["③ 法定調査・適正処理費（" + res.complianceBreakdownLabel + "）", formatYen(res.complianceExtraYen), ""],
      ["総事業費 合計（①＋②＋③ 税抜目安）", formatYen(res.grossCapex), ""],
      ["▲ 経産省 SII 省エネ投資促進支援事業（設備1/3補助）", "-" + formatYen(res.siiSubsidyYen), "row-total"],
      [
        "▲ " + res.prefName + " 中小企業脱炭素・高効率加算目安",
        "-" + formatYen(res.prefAddonYen),
        "row-total",
      ],
      ["補助金控除後 実質自己負担額", formatYen(res.netCapexYen), "row-net"],
      [
        "年間改善メリット（電気代削減 " +
          formatManYen(res.annualElecSavedYen) +
          "＋老朽保守リスク削減 " +
          formatManYen(res.legacyMaintPenaltyYen) +
          "）",
        formatYen(res.annualTotalBenefitYen) + "/年",
        "",
      ],
      ["実質投資回収年数 ／ 10年間累計純メリット", res.paybackYears.toFixed(1) + "年 ／ " + advSign + formatYen(res.tenYearNetAdvantage), "row-net"],
    ];

    document.getElementById("financial-breakdown-tbody").innerHTML = finRows
      .map(
        (r) =>
          "<tr class='" +
          r[2] +
          "'><td>" +
          escapeHtml(r[0]) +
          "</td><td class='num'>" +
          escapeHtml(r[1]) +
          "</td></tr>"
      )
      .join("");
    document.getElementById("subsidy-program-footnote").textContent =
      "適用想定制度：" +
      RULES.subsidy_rules.national_sii.program_name +
      " ／ " +
      res.prefProgram +
      "。" +
      RULES.subsidy_rules.national_sii.tax_incentive_note;

    // SVG 10年比較グラフ描画
    renderTcoSvgChart(res);

    // B2B CTA更新
    updateCtaSection(res);
  }

  function renderTcoSvgChart(res) {
    const svg = document.getElementById("tco-svg-chart");
    const W = 820;
    const H = 330;
    const padL = 78;
    const padR = 34;
    const padT = 28;
    const padB = 46;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    const maxVal = Math.max(...res.legacySeries, ...res.upgradeSeries, 1000000) * 1.14;

    const xOf = (yr) => padL + (yr / 10.0) * plotW;
    const yOf = (yen) => padT + plotH - (yen / maxVal) * plotH;

    let gridSvg = "";
    const yTicks = 5;
    for (let i = 0; i <= yTicks; i++) {
      const val = (maxVal / yTicks) * i;
      const y = yOf(val);
      const labelMan = Math.round(val / 10000).toLocaleString("ja-JP") + "万";
      gridSvg +=
        `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W - padR}" y2="${y.toFixed(1)}" stroke="#E2E8F0" stroke-width="1" />` +
        `<text x="${padL - 10}" y="${(y + 4).toFixed(1)}" text-anchor="end" font-family="'JetBrains Mono', 'Noto Sans JP', sans-serif" font-size="11" fill="#64748B">${labelMan}</text>`;
    }

    for (let yr = 0; yr <= 10; yr++) {
      const x = xOf(yr);
      gridSvg +=
        `<line x1="${x.toFixed(1)}" y1="${padT + plotH}" x2="${x.toFixed(1)}" y2="${padT + plotH + 5}" stroke="#CBD5E1" />` +
        `<text x="${x.toFixed(1)}" y="${padT + plotH + 20}" text-anchor="middle" font-family="'Plus Jakarta Sans', 'Noto Sans JP', sans-serif" font-size="11" fill="#475569">${yr === 0 ? "初年度" : yr + "年目"}</text>`;
    }

    const legacyPts = res.legacySeries.map((v, idx) => `${xOf(idx).toFixed(1)},${yOf(v).toFixed(1)}`).join(" ");
    const upgradePts = res.upgradeSeries.map((v, idx) => `${xOf(idx).toFixed(1)},${yOf(v).toFixed(1)}`).join(" ");

    // 損益分岐（投資回収）ポイントの座標計算
    let breakEvenSvg = "";
    for (let yr = 0; yr < 10; yr++) {
      const l0 = res.legacySeries[yr];
      const l1 = res.legacySeries[yr + 1];
      const u0 = res.upgradeSeries[yr];
      const u1 = res.upgradeSeries[yr + 1];
      if (l0 <= u0 && l1 >= u1 && l1 - l0 - (u1 - u0) !== 0) {
        const frac = (u0 - l0) / (l1 - l0 - (u1 - u0));
        const crossYr = yr + frac;
        const crossVal = u0;
        const cx = xOf(crossYr);
        const cy = yOf(crossVal);
        const badgeX = Math.min(W - padR - 132, Math.max(padL + 8, cx - 66));
        const badgeY = Math.max(padT + 6, cy - 38);
        breakEvenSvg =
          `<line x1="${cx.toFixed(1)}" y1="${cy.toFixed(1)}" x2="${cx.toFixed(1)}" y2="${padT + plotH}" stroke="#0077C2" stroke-dasharray="4 3" stroke-width="1.5" />` +
          `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="5.5" fill="#0077C2" stroke="#FFFFFF" stroke-width="2" />` +
          `<rect x="${badgeX.toFixed(1)}" y="${badgeY.toFixed(1)}" width="132" height="24" rx="6" fill="#0077C2" />` +
          `<text x="${(badgeX + 66).toFixed(1)}" y="${(badgeY + 15.5).toFixed(1)}" text-anchor="middle" font-family="'Plus Jakarta Sans', 'Noto Sans JP', sans-serif" font-size="11" font-weight="600" fill="#FFFFFF">投資回収 ${crossYr.toFixed(1)}年目</text>`;
        break;
      }
    }

    const legacyDots = res.legacySeries
      .map(
        (v, idx) =>
          `<circle cx="${xOf(idx).toFixed(1)}" cy="${yOf(v).toFixed(1)}" r="3.2" fill="#DC2626" />`
      )
      .join("");

    const endLegacyY = yOf(res.legacySeries[10]);
    const endUpgradeY = yOf(res.upgradeSeries[10]);

    svg.innerHTML =
      gridSvg +
      `<polygon points="${xOf(0).toFixed(1)},${(padT + plotH).toFixed(1)} ${legacyPts} ${xOf(10).toFixed(1)},${(padT + plotH).toFixed(1)}" fill="rgba(220,38,38,0.05)" />` +
      `<polyline fill="none" stroke="#DC2626" stroke-width="2.4" points="${legacyPts}" />` +
      `<polyline fill="none" stroke="#0077C2" stroke-width="2.4" points="${upgradePts}" />` +
      legacyDots +
      `<circle cx="${xOf(0).toFixed(1)}" cy="${yOf(res.upgradeSeries[0]).toFixed(1)}" r="3.8" fill="#0077C2" />` +
      `<circle cx="${xOf(10).toFixed(1)}" cy="${endUpgradeY.toFixed(1)}" r="3.8" fill="#0077C2" />` +
      breakEvenSvg +
      `<text x="${(xOf(10) - 6).toFixed(1)}" y="${Math.max(padT + 14, endLegacyY - 8).toFixed(1)}" text-anchor="end" font-family="'Plus Jakarta Sans', 'Noto Sans JP', sans-serif" font-size="11.5" font-weight="600" fill="#DC2626">10年放置累積ロス: ${formatManYen(res.legacySeries[10])}</text>` +
      `<text x="${(xOf(10) - 6).toFixed(1)}" y="${Math.min(padT + plotH - 8, endUpgradeY + 16).toFixed(1)}" text-anchor="end" font-family="'Plus Jakarta Sans', 'Noto Sans JP', sans-serif" font-size="11.5" font-weight="600" fill="#0077C2">補助金更新実質負担: ${formatManYen(res.upgradeSeries[10])}</text>` +
      `<text x="${padL}" y="16" font-family="'Plus Jakarta Sans', 'Noto Sans JP', sans-serif" font-size="11" font-weight="500" fill="#64748B">累積支出・損失額（万円）</text>`;
  }

  function updateCtaSection(res) {
    const channel = CTA_CONFIG.channels[res.equipType] || CTA_CONFIG.channels.cubicle;
    const mode = CTA_CONFIG.active_mode || "partner_form";

    document.getElementById("cta-headline").textContent = channel.headline;
    document.getElementById("cta-subheadline").textContent = channel.subheadline;
    document.getElementById("cta-urgency-box").textContent = channel.urgency_banner;

    const listEl = document.getElementById("cta-trust-list");
    listEl.innerHTML = (channel.trust_points || []).map((pt) => "<li>" + escapeHtml(pt) + "</li>").join("");

    let targetUrl = channel.partner_form_url;
    if (mode === "a8_affiliate") {
      targetUrl = channel.a8_affiliate_url;
    } else if (mode === "rentracks_affiliate") {
      targetUrl = channel.rentracks_affiliate_url;
    }

    if (targetUrl && targetUrl.toLowerCase().startsWith("mailto:")) {
      const baseMailto = targetUrl.split("?")[0];
      const equipLabel = res.equipType === "cubicle" ? "高圧受変電キュービクル・変圧器" : "業務用パッケージ空調";
      const capLabel = res.equipType === "cubicle" ? res.capacity + "kVA" : res.capacity + "馬力";
      const subjectStr =
        "【無料現地調査・補助金見積相談】" +
        equipLabel +
        "（" +
        res.prefName +
        "・" +
        res.year +
        "年製 " +
        capLabel +
        "）";
      const bodyStr = [
        "設備更新・補助金シミュレーター運営事務局 宛",
        "",
        "以下の試算条件にて、無料現地調査・省エネ補助金対応見積もりの相談を希望します。",
        "",
        "■ ご担当者様情報（ご記入ください）",
        "・会社名／事業場名：" + (document.getElementById("facility-name-input").value || ""),
        "・ご担当者様氏名：",
        "・お電話番号：",
        "・ご希望の連絡時間帯：",
        "",
        "■ シミュレーター診断結果サマリー",
        "・対象設備：" + equipLabel,
        "・メーカー：" + res.makerName,
        "・製造年：" + res.year + "年製",
        "・定格容量・台数：" + capLabel + " × " + res.unitCount,
        "・所在地／企業区分：" + res.prefName + "（" + (res.isSme ? "中小企業" : "大企業") + "）",
        "・PCB特措法判定：" + res.pcbEval.badge,
        "・工作物石綿調査判定：" + res.asbestosEval.badge,
        "・想定補助金合計：" + formatYen(res.totalSubsidyYen) + "（実質自己負担目安 " + formatYen(res.netCapexYen) + "）",
        "・年間コスト削減目安：" + formatYen(res.annualTotalBenefitYen) + "/年（実質投資回収 " + res.paybackYears.toFixed(1) + "年）",
      ].join("\r\n");
      targetUrl =
        baseMailto +
        "?subject=" +
        encodeURIComponent(subjectStr) +
        "&body=" +
        encodeURIComponent(bodyStr);
    } else if (channel.append_diagnostic_params && mode === "partner_form") {
      const params = new URLSearchParams({
        equip: res.equipType,
        maker: res.makerId,
        year: String(res.year),
        cap: String(res.capacity),
        units: String(res.unitCount),
        pcb: res.pcbEval.code,
        subsidy: String(res.totalSubsidyYen),
        pref: res.prefCode,
      });
      targetUrl += (targetUrl.includes("?") ? "&" : "?") + params.toString();
    }

    const linkEl = document.getElementById("cta-primary-link");
    linkEl.href = targetUrl;
    if (targetUrl && targetUrl.toLowerCase().startsWith("mailto:")) {
      linkEl.removeAttribute("target");
    } else {
      linkEl.setAttribute("target", "_blank");
    }
    linkEl.innerHTML =
      "<span>" +
      escapeHtml(channel.button_label) +
      '</span><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>';

    const prBadge = document.getElementById("cta-pr-badge");
    if (mode !== "partner_form" && CTA_CONFIG.compliance.show_pr_badge_in_affiliate_mode) {
      prBadge.textContent = CTA_CONFIG.compliance.pr_badge_text || "PR";
      prBadge.classList.remove("hidden");
    } else {
      prBadge.classList.add("hidden");
    }

    document.getElementById("cta-compliance-note").textContent =
      "運営形態：" + CTA_CONFIG.compliance.operator_role + "（本サイト上での直接課金・物品販売はありません）";
  }

  function buildRingiPlainText(res) {
    const unitLabel = res.equipType === "cubicle" ? res.capacity + "kVA" : res.capacity + "馬力";
    return [
      "【社内稟議・役員共有用 試算サマリー】",
      "対象拠点：" + (document.getElementById("facility-name-input").value || "自社事業場"),
      "対象設備：" + res.makerName + " " + res.year + "年製 " + unitLabel + " × " + res.unitCount,
      "--------------------------------------------------",
      "1. 法令リスク判定",
      "・PCB特措法（2027/3/31期限）：" + res.pcbEval.badge,
      "・工作物石綿事前調査（2026/1義務化）：" + res.asbestosEval.badge,
      "",
      "2. 省エネ効果（2026トップランナー基準更新）",
      "・年間削減電力量：" + formatNum(res.annualSavedKwh) + " kWh/年（CO2削減 -" + res.co2SavedTons + " t/年）",
      "・年間コスト改善額：" + formatYen(res.annualTotalBenefitYen) + "/年（電気代削減＋老朽保守リスク低減）",
      "",
      "3. 概算投資額・省エネ補助金・投資回収年数",
      "・総事業費目安：" + formatYen(res.grossCapex),
      "・想定補助金合計：-" + formatYen(res.totalSubsidyYen) + "（経産省SII 1/3補助＋" + res.prefName + "加算）",
      "・実質自己負担額：" + formatYen(res.netCapexYen),
      "・実質投資回収年数：" + res.paybackYears.toFixed(1) + " 年（10年累計純メリット " + formatYen(res.tenYearNetAdvantage) + "）",
    ].join("\n");
  }

  function setEquipmentType(equipType, makerOverride, capOverride) {
    document.getElementById("equipment-type").value = equipType;
    const tabCub = document.getElementById("tab-cubicle");
    const tabHvac = document.getElementById("tab-hvac");
    const cubOpts = document.getElementById("cubicle-only-options");

    if (equipType === "cubicle") {
      tabCub.classList.add("active");
      tabCub.setAttribute("aria-pressed", "true");
      tabHvac.classList.remove("active");
      tabHvac.setAttribute("aria-pressed", "false");
      cubOpts.classList.remove("hidden");
    } else {
      tabHvac.classList.add("active");
      tabHvac.setAttribute("aria-pressed", "true");
      tabCub.classList.remove("active");
      tabCub.setAttribute("aria-pressed", "false");
      cubOpts.classList.add("hidden");
    }

    populateManufacturers(equipType, makerOverride);
    populateCapacities(equipType, capOverride);
  }

  function bindEvents() {
    document.getElementById("tab-cubicle").addEventListener("click", () => {
      setEquipmentType("cubicle", "mitsubishi", 300);
      runDiagnostic();
    });

    document.getElementById("tab-hvac").addEventListener("click", () => {
      setEquipmentType("hvac", "daikin", 20);
      runDiagnostic();
    });

    const yearRange = document.getElementById("manufacturing-year-range");
    const yearInput = document.getElementById("manufacturing-year");
    yearRange.addEventListener("input", () => {
      yearInput.value = yearRange.value;
      runDiagnostic();
    });
    yearInput.addEventListener("input", () => {
      const v = parseInt(yearInput.value, 10);
      if (!Number.isNaN(v) && v >= 1970 && v <= 2020) {
        yearRange.value = String(v);
      }
      runDiagnostic();
    });

    const loadRange = document.getElementById("load-factor-range");
    const loadInput = document.getElementById("load-factor");
    loadRange.addEventListener("input", () => {
      loadInput.value = loadRange.value;
      runDiagnostic();
    });
    loadInput.addEventListener("input", () => {
      const v = parseInt(loadInput.value, 10);
      if (!Number.isNaN(v) && v >= 15 && v <= 95) {
        loadRange.value = String(v);
      }
      runDiagnostic();
    });

    document.querySelectorAll(".preset-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const val = chip.getAttribute("data-load");
        loadRange.value = val;
        loadInput.value = val;
        runDiagnostic();
      });
    });

    [
      "manufacturer-select",
      "capacity-select",
      "unit-count",
      "insulation-type",
      "upgrade-spec",
      "elec-rate",
      "prefecture-select",
      "sme-status",
      "facility-name-input",
      "dept-name-input",
    ].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener("change", runDiagnostic);
        el.addEventListener("input", runDiagnostic);
      }
    });

    document.getElementById("btn-parse-nameplate").addEventListener("click", () => {
      const raw = document.getElementById("nameplate-input").value;
      applyNameplateParse(raw);
    });

    document.getElementById("btn-clear-nameplate").addEventListener("click", () => {
      document.getElementById("nameplate-input").value = "";
      document.getElementById("ocr-parse-feedback").classList.add("hidden");
    });

    const triggerPrint = () => {
      runDiagnostic();
      window.print();
    };
    document.getElementById("btn-print-pdf").addEventListener("click", triggerPrint);
    document.getElementById("cta-secondary-print").addEventListener("click", triggerPrint);

    document.getElementById("btn-copy-ringi").addEventListener("click", async () => {
      if (!lastResult) return;
      const text = buildRingiPlainText(lastResult);
      const btn = document.getElementById("btn-copy-ringi");
      const labelSpan = btn.querySelector("span") || btn;
      try {
        await navigator.clipboard.writeText(text);
        const orig = labelSpan.textContent;
        labelSpan.textContent = "稟議テキストをコピーしました";
        setTimeout(() => {
          labelSpan.textContent = orig;
        }, 2200);
      } catch (_err) {
        window.prompt("以下の稟議用サマリーをコピーしてください：", text);
      }
    });
  }

  async function init() {
    try {
      const [rulesResp, ctaResp] = await Promise.all([
        fetch("./data/equipment_rules.json"),
        fetch("./data/cta_config.json"),
      ]);
      if (rulesResp.ok) {
        RULES = await rulesResp.json();
      }
      if (ctaResp.ok) {
        CTA_CONFIG = await ctaResp.json();
      }
    } catch (_fetchErr) {
      // ローカルfile://直開き時は内蔵FALLBACKデータでそのまま稼働
    }

    updateCountdownHeader();
    populatePrefectures();
    populateSampleButtons();
    populateReferenceLinks();
    setEquipmentType("cubicle", "mitsubishi", 300);
    bindEvents();
    runDiagnostic();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
