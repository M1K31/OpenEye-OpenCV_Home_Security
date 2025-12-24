/**
 * OpenEye Internationalization (i18n) System
 *
 * Provides multi-language support for the frontend.
 * Compatible with MagicMirror's translation system for ecosystem consistency.
 *
 * Usage:
 *   import { t, setLanguage, getLanguage } from './i18n';
 *
 *   // Translate a key
 *   t('dashboard.title') // Returns translated string
 *
 *   // With variable substitution
 *   t('cameras.count', { count: 5 }) // "5 cameras"
 *
 *   // Change language
 *   setLanguage('es');
 */

// Supported languages (subset of MagicMirror's 50+ languages)
export const SUPPORTED_LANGUAGES = {
  'en': 'English',
  'es': 'Español',
  'fr': 'Français',
  'de': 'Deutsch',
  'it': 'Italiano',
  'pt': 'Português',
  'nl': 'Nederlands',
  'pl': 'Polski',
  'ru': 'Русский',
  'ja': '日本語',
  'ko': '한국어',
  'zh-cn': '简体中文',
  'zh-tw': '繁體中文',
  'ar': 'العربية',
  'he': 'עברית',
  'hi': 'हिन्दी',
  'tr': 'Türkçe',
  'sv': 'Svenska',
  'da': 'Dansk',
  'fi': 'Suomi',
  'no': 'Norsk',
  'cs': 'Čeština',
  'uk': 'Українська',
  'th': 'ไทย',
  'vi': 'Tiếng Việt',
};

// Current language state
let currentLanguage = 'en';
let translations = {};
let fallbackTranslations = {};

/**
 * Load translations for a language
 * @param {string} lang - Language code
 * @returns {Promise<object>} Translations object
 */
export async function loadTranslations(lang) {
  try {
    const module = await import(`./locales/${lang}.json`);
    return module.default || module;
  } catch (error) {
    console.warn(`[i18n] Translations for '${lang}' not found, using English fallback`);
    if (lang !== 'en') {
      return loadTranslations('en');
    }
    return {};
  }
}

/**
 * Initialize i18n system
 * @param {string} lang - Initial language (default: browser language or 'en')
 */
export async function initI18n(lang = null) {
  // Detect language from:
  // 1. Provided parameter
  // 2. localStorage
  // 3. Browser language
  // 4. Default to English
  const detectedLang = lang ||
    localStorage.getItem('openeye_language') ||
    navigator.language?.split('-')[0] ||
    'en';

  // Normalize language code
  currentLanguage = detectedLang.toLowerCase();
  if (currentLanguage.includes('-')) {
    // Handle zh-CN, zh-TW specifically
    if (currentLanguage.startsWith('zh')) {
      currentLanguage = currentLanguage === 'zh-tw' ? 'zh-tw' : 'zh-cn';
    } else {
      currentLanguage = currentLanguage.split('-')[0];
    }
  }

  // Check if language is supported
  if (!SUPPORTED_LANGUAGES[currentLanguage]) {
    console.warn(`[i18n] Language '${currentLanguage}' not supported, falling back to English`);
    currentLanguage = 'en';
  }

  // Load translations
  fallbackTranslations = await loadTranslations('en');
  if (currentLanguage !== 'en') {
    translations = await loadTranslations(currentLanguage);
  } else {
    translations = fallbackTranslations;
  }

  // Save preference
  localStorage.setItem('openeye_language', currentLanguage);

  // Set document language attribute
  document.documentElement.lang = currentLanguage;

  // Set RTL direction for Arabic/Hebrew
  if (['ar', 'he'].includes(currentLanguage)) {
    document.documentElement.dir = 'rtl';
  } else {
    document.documentElement.dir = 'ltr';
  }

  console.log(`[i18n] Initialized with language: ${currentLanguage}`);
  return currentLanguage;
}

/**
 * Get nested value from object using dot notation
 * @param {object} obj - Object to search
 * @param {string} path - Dot-notation path (e.g., 'dashboard.cameras.title')
 * @returns {string|undefined} Value or undefined
 */
function getNestedValue(obj, path) {
  return path.split('.').reduce((current, key) =>
    current && current[key] !== undefined ? current[key] : undefined, obj);
}

/**
 * Translate a key
 * @param {string} key - Translation key (dot notation supported)
 * @param {object} variables - Variables for substitution
 * @returns {string} Translated string or key if not found
 */
export function t(key, variables = {}) {
  // Try current language first
  let translation = getNestedValue(translations, key);

  // Fallback to English
  if (translation === undefined) {
    translation = getNestedValue(fallbackTranslations, key);
  }

  // Return key if not found
  if (translation === undefined) {
    console.warn(`[i18n] Missing translation: ${key}`);
    return key;
  }

  // Variable substitution: {variableName}
  if (variables && typeof translation === 'string') {
    translation = translation.replace(/\{(\w+)\}/g, (match, varName) => {
      return variables[varName] !== undefined ? variables[varName] : match;
    });
  }

  return translation;
}

/**
 * Get current language
 * @returns {string} Current language code
 */
export function getLanguage() {
  return currentLanguage;
}

/**
 * Set language
 * @param {string} lang - Language code
 * @returns {Promise<string>} New language code
 */
export async function setLanguage(lang) {
  if (!SUPPORTED_LANGUAGES[lang]) {
    console.warn(`[i18n] Language '${lang}' not supported`);
    return currentLanguage;
  }

  return initI18n(lang);
}

/**
 * Get all supported languages
 * @returns {object} Language code -> name mapping
 */
export function getSupportedLanguages() {
  return { ...SUPPORTED_LANGUAGES };
}

/**
 * Check if a translation key exists
 * @param {string} key - Translation key
 * @returns {boolean} True if key exists
 */
export function hasTranslation(key) {
  return getNestedValue(translations, key) !== undefined ||
         getNestedValue(fallbackTranslations, key) !== undefined;
}

/**
 * Get direction for current language
 * @returns {'ltr'|'rtl'} Text direction
 */
export function getTextDirection() {
  return ['ar', 'he'].includes(currentLanguage) ? 'rtl' : 'ltr';
}

/**
 * Format a number according to current locale
 * @param {number} num - Number to format
 * @param {object} options - Intl.NumberFormat options
 * @returns {string} Formatted number
 */
export function formatNumber(num, options = {}) {
  return new Intl.NumberFormat(currentLanguage, options).format(num);
}

/**
 * Format a date according to current locale
 * @param {Date|string|number} date - Date to format
 * @param {object} options - Intl.DateTimeFormat options
 * @returns {string} Formatted date
 */
export function formatDate(date, options = { dateStyle: 'medium' }) {
  return new Intl.DateTimeFormat(currentLanguage, options).format(new Date(date));
}

/**
 * Format relative time (e.g., "5 minutes ago")
 * @param {Date|string|number} date - Date to compare
 * @returns {string} Relative time string
 */
export function formatRelativeTime(date) {
  const rtf = new Intl.RelativeTimeFormat(currentLanguage, { numeric: 'auto' });
  const diff = new Date(date) - new Date();
  const diffSeconds = Math.round(diff / 1000);
  const diffMinutes = Math.round(diff / 60000);
  const diffHours = Math.round(diff / 3600000);
  const diffDays = Math.round(diff / 86400000);

  if (Math.abs(diffSeconds) < 60) {
    return rtf.format(diffSeconds, 'second');
  } else if (Math.abs(diffMinutes) < 60) {
    return rtf.format(diffMinutes, 'minute');
  } else if (Math.abs(diffHours) < 24) {
    return rtf.format(diffHours, 'hour');
  } else {
    return rtf.format(diffDays, 'day');
  }
}

// React Hook for translations (optional, for React components)
export function useTranslation() {
  return {
    t,
    language: currentLanguage,
    setLanguage,
    formatNumber,
    formatDate,
    formatRelativeTime,
    direction: getTextDirection(),
  };
}

// Initialize on module load with default language
initI18n();

export default {
  t,
  initI18n,
  setLanguage,
  getLanguage,
  getSupportedLanguages,
  hasTranslation,
  formatNumber,
  formatDate,
  formatRelativeTime,
  useTranslation,
};
