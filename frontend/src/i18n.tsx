import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

export type Lang = 'en' | 'fa';

const translations: Record<Lang, Record<string, string>> = {
  en: {
    // Nav
    dashboard: 'Dashboard',
    newScan: 'New Scan',
    agents: 'Agents',
    settings: 'Settings',
    systemOnline: 'System Online',
    users: 'Users',
    tools: 'Tools',
    audit: 'Audit Log',
    assets: 'Assets',
    // Assets
    assetInventory: 'Asset Inventory',
    assetsDiscovered: 'assets discovered across all scans',
    searchByHost: 'Search by host...',
    allTypes: 'All Types',
    hosts: 'Hosts',
    services: 'Services',
    noAssets: 'No assets discovered yet',
    runScanToDiscover: 'Run a scan to discover assets',
    services_label: 'services',
    owner: 'Owner',
    notes: 'Notes',
    editAsset: 'Edit Asset',
    addNotes: 'Add notes about this asset...',
    assignOwner: 'Assign owner...',
    // Dashboard
    overview: 'Overview',
    totalScans: 'Total Scans',
    running: 'Running',
    completed: 'Completed',
    findings: 'Findings',
    recentEngagements: 'Recent Engagements',
    noEngagements: 'No engagements yet. Create your first scan!',
    newEngagement: 'New Engagement',
    view: 'View',
    target: 'Target',
    status: 'Status',
    created: 'Created',
    actions: 'Actions',
    // New Scan
    createNewScan: 'Create New Scan',
    scanName: 'Scan Name',
    scanNamePlaceholder: 'e.g. Internal Network Audit',
    targetScope: 'Target Scope',
    targetPlaceholder: 'e.g. 192.168.1.0/24 or scanme.nmap.org',
    addTarget: 'Add Target',
    scanMode: 'Scan Mode',
    quick: 'Quick',
    standard: 'Standard',
    deep: 'Deep',
    quickDesc: 'Top ports, fast scan',
    standardDesc: 'All common ports + services',
    deepDesc: 'Full port range, aggressive',
    reportLevel: 'Report Level',
    minimal: 'Minimal',
    medium: 'Medium',
    detailed: 'Detailed',
    exploitation: 'Exploitation',
    enableExploitation: 'Enable Exploitation Phase',
    exploitWarning: 'Exploitation attempts to actively compromise targets. Only enable with written authorization.',
    startScan: 'Start Scan',
    starting: 'Starting...',
    // Scan Detail
    workflow: 'Workflow',
    liveLogs: 'Live Logs',
    noActions: 'No actions recorded yet',
    notStarted: 'Not started',
    waitingEvents: 'Waiting for events...',
    live: 'Live',
    offline: 'Offline',
    remediation: 'Remediation',
    noFindings: 'No findings yet',
    tokens: 'tokens',
    completedLabel: 'Completed',
    runningLabel: 'Running',
    // Agents
    configureAgent: 'Configure agent behavior and prompts',
    saveChanges: 'Save Changes',
    temperature: 'Temperature',
    precise: 'Precise',
    creative: 'Creative',
    maxTokens: 'Max Tokens',
    enabled: 'Enabled',
    disabled: 'Disabled',
    systemPrompt: 'System Prompt',
    characters: 'characters',
    // Settings
    llmConfiguration: 'LLM Configuration',
    baseUrl: 'Base URL',
    apiKey: 'API Key',
    model: 'Model',
    toolboxManagement: 'Toolbox Management',
    language: 'Language',
    // Phases
    phaseRecon: 'Reconnaissance',
    phaseScanner: 'Vulnerability Scan',
    phaseAnalysis: 'Analysis',
    phaseExploit: 'Exploitation',
    phaseReport: 'Report',
    // Agent descriptions
    agentDescRecon: 'Port scanning, service detection',
    agentDescScanner: 'Vulnerability scanning, exploit check',
    agentDescAnalyzer: 'CVE analysis, exploit verification',
    agentDescExploit: 'Exploit execution, payload delivery',
    agentDescReport: 'Report generation, remediation',
  },
  fa: {
    dashboard: 'داشبورد',
    newScan: 'اسکن جدید',
    agents: 'ایجنت‌ها',
    settings: 'تنظیمات',
    systemOnline: 'سیستم آنلاین',
    users: 'کاربران',
    tools: 'ابزارها',
    audit: 'گزارش رویدادها',
    assets: 'دارایی‌ها',
    overview: 'نمای کلی',
    totalScans: 'کل اسکن‌ها',
    running: 'در حال اجرا',
    completed: 'تکمیل شده',
    findings: 'یافته‌ها',
    recentEngagements: 'ارزیابی‌های اخیر',
    noEngagements: 'هنوز ارزیابی وجود ندارد. اولین اسکن خود را بسازید!',
    newEngagement: 'ارزیابی جدید',
    view: 'مشاهده',
    target: 'هدف',
    status: 'وضعیت',
    created: 'تاریخ ایجاد',
    actions: 'اقدامات',
    createNewScan: 'ایجاد اسکن جدید',
    scanName: 'نام اسکن',
    scanNamePlaceholder: 'مثلاً: ممیزی شبکه داخلی',
    targetScope: 'محدوده هدف',
    targetPlaceholder: 'مثلاً: 192.168.1.0/24 یا scanme.nmap.org',
    addTarget: 'افزودن هدف',
    scanMode: 'حالت اسکن',
    quick: 'سریع',
    standard: 'استاندارد',
    deep: 'عمیق',
    quickDesc: 'پورت‌های اصلی، اسکن سریع',
    standardDesc: 'همه پورت‌های رایج + سرویس‌ها',
    deepDesc: 'کل محدوده پورت‌ها، تهاجمی',
    reportLevel: 'سطح گزارش',
    minimal: 'حداقلی',
    medium: 'متوسط',
    detailed: 'کامل',
    exploitation: 'بهره‌برداری',
    enableExploitation: 'فعال‌سازی مرحله بهره‌برداری',
    exploitWarning: 'بهره‌برداری تلاش می‌کند اهداف را فعالانه درگیر کند. فقط با مجوز کتبی فعال کنید.',
    startScan: 'شروع اسکن',
    starting: 'در حال شروع...',
    workflow: 'گردش کار',
    liveLogs: 'لاگ‌های زنده',
    noActions: 'هنوز اقدامی ثبت نشده',
    notStarted: 'شروع نشده',
    waitingEvents: 'در انتظار رویدادها...',
    live: 'زنده',
    offline: 'آفلاین',
    remediation: 'راهکار رفع',
    noFindings: 'هنوز یافته‌ای وجود ندارد',
    tokens: 'توکن',
    completedLabel: 'تکمیل شده',
    runningLabel: 'در حال اجرا',
    configureAgent: 'پیکربندی رفتار و پرامپت ایجنت',
    saveChanges: 'ذخیره تغییرات',
    temperature: 'دما',
    precise: 'دقیق',
    creative: 'خلاقانه',
    maxTokens: 'حداکثر توکن',
    enabled: 'فعال',
    disabled: 'غیرفعال',
    systemPrompt: 'پرامپت سیستم',
    characters: 'کاراکتر',
    llmConfiguration: 'پیکربندی LLM',
    baseUrl: 'آدرس پایه',
    apiKey: 'کلید API',
    model: 'مدل',
    toolboxManagement: 'مدیریت جعبه‌ابزار',
    language: 'زبان',
    phaseRecon: 'شناسایی',
    phaseScanner: 'اسکن آسیب‌پذیری',
    phaseAnalysis: 'تحلیل',
    phaseExploit: 'بهره‌برداری',
    phaseReport: 'گزارش',
    agentDescRecon: 'اسکن پورت، شناسایی سرویس',
    agentDescScanner: 'اسکن آسیب‌پذیری، بررسی اکسپلویت',
    agentDescAnalyzer: 'تحلیل CVE، تأیید اکسپلویت',
    agentDescExploit: 'اجرای اکسپلویت، تحویل پیلود',
    agentDescReport: 'تولید گزارش، راهکار رفع',
  },
};

interface LangContextType {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string) => string;
  dir: 'ltr' | 'rtl';
}

const LangContext = createContext<LangContextType>({
  lang: 'en',
  setLang: () => {},
  t: (k) => k,
  dir: 'ltr',
});

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    return (localStorage.getItem('netactor_lang') as Lang) || 'en';
  });

  const dir: 'ltr' | 'rtl' = lang === 'fa' ? 'rtl' : 'ltr';

  useEffect(() => {
    document.documentElement.setAttribute('dir', dir);
    document.documentElement.setAttribute('lang', lang);
  }, [lang, dir]);

  const setLang = (l: Lang) => {
    setLangState(l);
    localStorage.setItem('netactor_lang', l);
  };

  const t = (key: string) => translations[lang][key] || translations.en[key] || key;

  return (
    <LangContext.Provider value={{ lang, setLang, t, dir }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang() {
  return useContext(LangContext);
}
