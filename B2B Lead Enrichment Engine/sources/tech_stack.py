import re
from typing import Optional, List, Dict, Set, Any
from bs4 import BeautifulSoup


class TechStackDetector:
    """
    Интеллектуальный детектор технологического стека, CMS, CRM и маркетинговых систем сайта:
    Позволяет B2B-компаниям мгновенно сегментировать клиентов по используемым IT-системам
    (например: "Все компании на 1С-Битрикс без CRM" или "Пользователи amoCRM").
    """

    SIGNATURES = {
        # CMS и платформы
        "1C-Bitrix": [r"/bitrix/", r"bitrix_sessid", r"BX\.ready", r"1c-bitrix"],
        "Tilda": [r"tilda\.ws", r"tildaBlocks", r"tilda-", r"static\.tildacdn\.com"],
        "WordPress": [r"wp-content", r"wp-includes", r"wordpress"],
        "OpenCart": [r"catalog/view/theme", r"index\.php\?route="],
        "InSales": [r"insales\.ru", r"insales-"],
        "Webasyst / Shop-Script": [r"wa-content", r"wa-apps"],
        "MODX": [r"assets/templates/", r"modx"],
        "Drupal": [r"drupal\.js", r"Drupal\.settings"],

        # Фреймворки и Frontend
        "React": [r"react-root", r"data-reactroot", r"_reactInternal", r"react\.production"],
        "Vue.js": [r"data-v-", r"vue\.js", r"vue\.min\.js"],
        "Next.js": [r"__next", r"/_next/static"],
        "Angular": [r"ng-version", r"ng-app"],

        # CRM и онлайн-консультанты (B2B Lead Capture)
        "amoCRM": [r"amocrm\.ru", r"amocrm_chat", r"pipedrive", r"amocrm"],
        "Bitrix24 CRM Widget": [r"b24-form", r"bitrix24\.ru", r"bx24", r"b24form"],
        "JivoSite": [r"code\.jivosite\.com", r"jivo\.ru", r"jivo_"],
        "Carrot quest": [r"carrotquest\.io", r"carrotquest"],
        "Envybox": [r"envybox\.io"],
        "Marquiz": [r"marquiz\.ru"],
        "Calltouch": [r"calltouch\.ru", r"mod\.calltouch"],
        "Roistat": [r"roistat\.com", r"roistat_"],

        # Аналитика
        "Yandex Metrika": [r"mc\.yandex\.ru", r"ym\(", r"w\.yaCounter"],
        "Google Analytics": [r"googletagmanager\.com", r"google-analytics\.com", r"gtag\("],

        # Хостинг и Cloud
        "DDoS-Guard": [r"ddos-guard\.net"],
        "Cloudflare": [r"cloudflare\.com", r"cf-browser-verification"],
        "Selectel": [r"selectel\.ru"]
    }

    def detect_technologies(self, html_text: str, headers: Optional[Dict[str, str]] = None) -> List[str]:
        """Анализ HTML-кода и заголовков для определения стека."""
        if not html_text:
            return []

        detected: Set[str] = set()

        for tech_name, patterns in self.SIGNATURES.items():
            for pat in patterns:
                if re.search(pat, html_text, re.IGNORECASE):
                    detected.add(tech_name)
                    break

        if headers:
            h_str = " ".join([f"{k}:{v}" for k, v in headers.items()]).lower()
            if "bitrix" in h_str:
                detected.add("1C-Bitrix")
            if "cloudflare" in h_str:
                detected.add("Cloudflare")
            if "nginx" in h_str:
                detected.add("Nginx")

        return sorted(list(detected))
