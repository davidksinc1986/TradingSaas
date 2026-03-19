from __future__ import annotations

from fastapi import Request

SUPPORTED_LOCALES = ("es", "en", "fr", "pt")
DEFAULT_LOCALE = "es"
AUTO_LOCALE = "auto"


def normalize_locale(value: str | None) -> str | None:
    raw = (value or "").strip().lower()
    if not raw:
        return None
    code = raw.split(",")[0].split(";")[0].strip().split("-")[0]
    if code == AUTO_LOCALE:
        return AUTO_LOCALE
    if code in SUPPORTED_LOCALES:
        return code
    return None


def detect_header_locale(header_value: str | None) -> str:
    header = (header_value or "").lower()
    for chunk in header.split(","):
        code = normalize_locale(chunk)
        if code in SUPPORTED_LOCALES:
            return code
    return DEFAULT_LOCALE


TRANSLATIONS = {
    "es": {
        "app.name": "Trading Snake Mafia",
        "app.tagline": "quantum computing mathematics",
        "nav.home": "Inicio",
        "nav.dashboard": "Dashboard",
        "nav.admin": "Admin",
        "nav.login": "Login",
        "nav.logout": "Salir",
        "lang.label": "Idioma",
        "lang.auto": "Automático",
        "nav.lang_auto": "Auto",
        "modal.guide": "Guía",
        "modal.close": "Cerrar",
        "modal.required_data": "Datos requeridos",
        "modal.step_by_step": "Paso a paso",
        "home.pill": "Estrategias multi-mercado, ejecución inteligente",
        "home.title": "Construye tu ecosistema de trading premium con visión de crecimiento patrimonial.",
        "home.body": "Conecta brokers, exchanges y señales desde un solo lugar. Diseñado para operar con disciplina, automatizar decisiones y convertir análisis en resultados consistentes de largo plazo.",
        "home.cta_enter": "Entrar al ecosistema",
        "home.cta_dashboard": "Ver dashboard",
        "home.login_title": "Inicia sesión",
        "home.login_hint": "Accede a tu panel privado y gestiona tus conectores de forma segura.",
        "home.faq_title": "FAQ · ¿Por qué esta app?",
        "login.title": "Bienvenido de vuelta",
        "login.subtitle": "Tu zona privada para gestión de conectores y estrategias.",
        "login.button": "Ingresar al dashboard",
    },
    "en": {
        "app.name": "Trading Snake Mafia",
        "app.tagline": "quantum computing mathematics",
        "nav.home": "Home",
        "nav.dashboard": "Dashboard",
        "nav.admin": "Admin",
        "nav.login": "Login",
        "nav.logout": "Logout",
        "lang.label": "Language",
        "lang.auto": "Automatic",
        "nav.lang_auto": "Auto",
        "modal.guide": "Guide",
        "modal.close": "Close",
        "modal.required_data": "Required data",
        "modal.step_by_step": "Step by step",
        "home.pill": "Multi-market strategies, smart execution",
        "home.title": "Build your premium trading ecosystem with a long-term wealth vision.",
        "home.body": "Connect brokers, exchanges and signals from one place. Built to trade with discipline, automate decisions and convert analysis into consistent long-term outcomes.",
        "home.cta_enter": "Enter ecosystem",
        "home.cta_dashboard": "Open dashboard",
        "home.login_title": "Sign in",
        "home.login_hint": "Access your private panel and manage your connectors securely.",
        "home.faq_title": "FAQ · Why this app?",
        "login.title": "Welcome back",
        "login.subtitle": "Your private zone for connectors and strategy management.",
        "login.button": "Go to dashboard",
    },
    "pt": {
        "app.name": "Trading Snake Mafia",
        "app.tagline": "quantum computing mathematics",
        "nav.home": "Início",
        "nav.dashboard": "Painel",
        "nav.admin": "Admin",
        "nav.login": "Login",
        "nav.logout": "Sair",
        "lang.label": "Idioma",
        "lang.auto": "Automático",
        "nav.lang_auto": "Auto",
        "modal.guide": "Guia",
        "modal.close": "Fechar",
        "modal.required_data": "Dados obrigatórios",
        "modal.step_by_step": "Passo a passo",
        "home.pill": "Estratégias multi-mercado, execução inteligente",
        "home.title": "Construa seu ecossistema premium de trading com visão de patrimônio.",
        "home.body": "Conecte corretoras, exchanges e sinais em um só lugar. Feito para operar com disciplina, automatizar decisões e transformar análise em resultados consistentes.",
        "home.cta_enter": "Entrar no ecossistema",
        "home.cta_dashboard": "Ver painel",
        "home.login_title": "Entrar",
        "home.login_hint": "Acesse seu painel privado e gerencie seus conectores com segurança.",
        "home.faq_title": "FAQ · Por que este app?",
        "login.title": "Bem-vindo de volta",
        "login.subtitle": "Sua área privada para gestão de conectores e estratégias.",
        "login.button": "Entrar no painel",
    },
    "fr": {
        "app.name": "Trading Snake Mafia",
        "app.tagline": "quantum computing mathematics",
        "nav.home": "Accueil",
        "nav.dashboard": "Dashboard",
        "nav.admin": "Admin",
        "nav.login": "Connexion",
        "nav.logout": "Sortir",
        "lang.label": "Langue",
        "lang.auto": "Automatique",
        "nav.lang_auto": "Auto",
        "modal.guide": "Guide",
        "modal.close": "Fermer",
        "modal.required_data": "Données requises",
        "modal.step_by_step": "Étapes",
        "home.pill": "Stratégies multi-marché, exécution intelligente",
        "home.title": "Construisez votre écosystème trading premium orienté croissance patrimoniale.",
        "home.body": "Connectez brokers, exchanges et signaux en un seul endroit. Conçu pour trader avec discipline, automatiser les décisions et transformer l'analyse en résultats réguliers.",
        "home.cta_enter": "Entrer dans l'écosystème",
        "home.cta_dashboard": "Voir dashboard",
        "home.login_title": "Se connecter",
        "home.login_hint": "Accédez à votre espace privé et gérez vos connecteurs en sécurité.",
        "home.faq_title": "FAQ · Pourquoi cette app ?",
        "login.title": "Bon retour",
        "login.subtitle": "Votre espace privé pour gérer connecteurs et stratégies.",
        "login.button": "Aller au dashboard",
    },
}


def detect_locale(request: Request) -> str:
    cookie_lang = normalize_locale(request.cookies.get("lang"))
    if cookie_lang in SUPPORTED_LOCALES:
        return cookie_lang
    return detect_header_locale(request.headers.get("accept-language"))


def translate(key: str, locale: str) -> str:
    active_locale = normalize_locale(locale) or DEFAULT_LOCALE
    return TRANSLATIONS.get(active_locale, TRANSLATIONS[DEFAULT_LOCALE]).get(key, TRANSLATIONS[DEFAULT_LOCALE].get(key, key))
