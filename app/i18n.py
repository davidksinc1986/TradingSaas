from __future__ import annotations

from fastapi import Request

SUPPORTED_LOCALES = ("es", "en", "pt", "fr")

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
    cookie_lang = (request.cookies.get("lang") or "").lower().strip()
    if cookie_lang in SUPPORTED_LOCALES:
        return cookie_lang

    header = (request.headers.get("accept-language") or "").lower()
    for chunk in header.split(","):
        code = chunk.split(";")[0].strip().split("-")[0]
        if code in SUPPORTED_LOCALES:
            return code
    return "es"


def translate(key: str, locale: str) -> str:
    return TRANSLATIONS.get(locale, TRANSLATIONS["es"]).get(key, TRANSLATIONS["es"].get(key, key))
