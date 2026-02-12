"""
Localization support for notification templates.

Provides localized strings for all supported markets and languages.
Templates use placeholders that are filled in at render time.

Supported locales:
- en_US: English (United States)
- en_GB: English (United Kingdom)
- es_US: Spanish (United States)
- es_MX: Spanish (Mexico)
- fr_CA: French (Canada)
- de_DE: German (Germany)
- pt_BR: Portuguese (Brazil)
"""

from typing import Dict

# Placeholder markers used in templates:
# {first_name} - Customer's first name
# {percentage} - Threshold percentage (e.g., 50)
# {current_usage} - Current usage amount with currency
# {threshold} - Threshold amount with currency
# {usage_url} - Link to usage details
# {buy_pass_url} - Link to purchase international pass
# {change_plan_url} - Link to plan upgrade options
# {billing_cycle_end} - End date of current billing cycle


LOCALIZED_STRINGS: Dict[str, Dict[str, str]] = {
    "en_US": {
        # SMS (160 char limit for single segment)
        "sms_50_percent_body": (
            "{first_name}, you've used {percentage}% of your international allowance "
            "({current_usage} of {threshold}). View details & options: {usage_url}"
        ),

        # Email
        "email_50_percent_subject": (
            "You've reached {percentage}% of your international usage allowance"
        ),
        "email_50_percent_body": (
            "Hi {first_name},\n\n"
            "You've used {percentage}% of your international usage allowance for this billing cycle.\n\n"
            "Current usage: {current_usage}\n"
            "Your allowance: {threshold}\n"
            "Billing cycle ends: {billing_cycle_end}\n\n"
            "To avoid overage charges, consider these options:\n"
            "- Buy an International Pass: {buy_pass_url}\n"
            "- Upgrade your plan: {change_plan_url}\n\n"
            "View your detailed usage: {usage_url}\n\n"
            "Thank you for being a valued customer.\n\n"
            "Best regards,\n"
            "Your Mobile Team"
        ),
        "email_50_percent_html": (
            """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>International Usage Alert</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 8px 8px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">International Usage Alert</h1>
    </div>

    <div style="background: #f9f9f9; padding: 20px; border: 1px solid #ddd; border-top: none;">
        <p>Hi {first_name},</p>

        <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 4px; padding: 15px; margin: 20px 0;">
            <strong style="color: #856404;">⚠️ You've used {percentage}% of your international usage allowance</strong>
        </div>

        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #ddd;"><strong>Current Usage:</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #ddd; text-align: right;">{current_usage}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #ddd;"><strong>Your Allowance:</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #ddd; text-align: right;">{threshold}</td>
            </tr>
            <tr>
                <td style="padding: 10px;"><strong>Billing Cycle Ends:</strong></td>
                <td style="padding: 10px; text-align: right;">{billing_cycle_end}</td>
            </tr>
        </table>

        <h3 style="color: #333; margin-top: 30px;">Recommended Actions</h3>
        <p>To avoid overage charges, consider these options:</p>

        <div style="margin: 20px 0;">
            <a href="{buy_pass_url}" style="display: inline-block; background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin-right: 10px; margin-bottom: 10px;">Buy an International Pass</a>
            <a href="{change_plan_url}" style="display: inline-block; background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin-bottom: 10px;">Upgrade Your Plan</a>
        </div>

        <p style="margin-top: 30px;">
            <a href="{usage_url}" style="color: #667eea;">View your detailed usage →</a>
        </p>

        <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

        <p style="color: #666; font-size: 14px;">
            Thank you for being a valued customer.<br>
            Best regards,<br>
            <strong>Your Mobile Team</strong>
        </p>
    </div>

    <div style="background: #333; color: #999; padding: 15px; border-radius: 0 0 8px 8px; font-size: 12px; text-align: center;">
        <p style="margin: 0;">This is an automated message. Please do not reply directly to this email.</p>
    </div>
</body>
</html>"""
        ),

        # Push notification
        "push_50_percent_title": "International Usage Alert",
        "push_50_percent_body": (
            "{first_name}, you've used {percentage}% of your international allowance ({current_usage}). "
            "Tap to view options."
        ),
    },

    "en_GB": {
        "sms_50_percent_body": (
            "{first_name}, you've used {percentage}% of your international allowance "
            "({current_usage} of {threshold}). View details & options: {usage_url}"
        ),
        "email_50_percent_subject": (
            "You've reached {percentage}% of your international usage allowance"
        ),
        "email_50_percent_body": (
            "Hi {first_name},\n\n"
            "You've used {percentage}% of your international usage allowance for this billing cycle.\n\n"
            "Current usage: {current_usage}\n"
            "Your allowance: {threshold}\n"
            "Billing cycle ends: {billing_cycle_end}\n\n"
            "To avoid additional charges, consider these options:\n"
            "- Buy an International Pass: {buy_pass_url}\n"
            "- Upgrade your plan: {change_plan_url}\n\n"
            "View your detailed usage: {usage_url}\n\n"
            "Thank you for being a valued customer.\n\n"
            "Kind regards,\n"
            "Your Mobile Team"
        ),
        "email_50_percent_html": (
            """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>International Usage Alert</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #667eea;">International Usage Alert</h1>
    <p>Hi {first_name},</p>
    <p><strong>You've used {percentage}% of your international usage allowance.</strong></p>
    <p>Current usage: {current_usage} | Allowance: {threshold}</p>
    <p>Billing cycle ends: {billing_cycle_end}</p>
    <p>Recommended actions:</p>
    <ul>
        <li><a href="{buy_pass_url}">Buy an International Pass</a></li>
        <li><a href="{change_plan_url}">Upgrade your plan</a></li>
    </ul>
    <p><a href="{usage_url}">View detailed usage</a></p>
    <p>Kind regards,<br>Your Mobile Team</p>
</body>
</html>"""
        ),
        "push_50_percent_title": "International Usage Alert",
        "push_50_percent_body": (
            "{first_name}, you've used {percentage}% of your international allowance ({current_usage}). "
            "Tap to view options."
        ),
    },

    "es_US": {
        "sms_50_percent_body": (
            "{first_name}, has usado {percentage}% de tu límite internacional "
            "({current_usage} de {threshold}). Ver detalles: {usage_url}"
        ),
        "email_50_percent_subject": (
            "Has alcanzado el {percentage}% de tu límite de uso internacional"
        ),
        "email_50_percent_body": (
            "Hola {first_name},\n\n"
            "Has usado el {percentage}% de tu límite de uso internacional para este ciclo de facturación.\n\n"
            "Uso actual: {current_usage}\n"
            "Tu límite: {threshold}\n"
            "El ciclo de facturación termina: {billing_cycle_end}\n\n"
            "Para evitar cargos adicionales, considera estas opciones:\n"
            "- Comprar un Pase Internacional: {buy_pass_url}\n"
            "- Mejorar tu plan: {change_plan_url}\n\n"
            "Ver tu uso detallado: {usage_url}\n\n"
            "Gracias por ser un cliente valioso.\n\n"
            "Saludos,\n"
            "Tu Equipo Móvil"
        ),
        "email_50_percent_html": (
            """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Alerta de Uso Internacional</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #667eea;">Alerta de Uso Internacional</h1>
    <p>Hola {first_name},</p>
    <p><strong>Has usado el {percentage}% de tu límite de uso internacional.</strong></p>
    <p>Uso actual: {current_usage} | Límite: {threshold}</p>
    <p>El ciclo de facturación termina: {billing_cycle_end}</p>
    <p>Acciones recomendadas:</p>
    <ul>
        <li><a href="{buy_pass_url}">Comprar un Pase Internacional</a></li>
        <li><a href="{change_plan_url}">Mejorar tu plan</a></li>
    </ul>
    <p><a href="{usage_url}">Ver uso detallado</a></p>
    <p>Saludos,<br>Tu Equipo Móvil</p>
</body>
</html>"""
        ),
        "push_50_percent_title": "Alerta de Uso Internacional",
        "push_50_percent_body": (
            "{first_name}, has usado {percentage}% de tu límite internacional ({current_usage}). "
            "Toca para ver opciones."
        ),
    },

    "es_MX": {
        "sms_50_percent_body": (
            "{first_name}, has usado {percentage}% de tu límite internacional "
            "({current_usage} de {threshold}). Ver detalles: {usage_url}"
        ),
        "email_50_percent_subject": (
            "Has alcanzado el {percentage}% de tu límite de uso internacional"
        ),
        "email_50_percent_body": (
            "Hola {first_name},\n\n"
            "Has usado el {percentage}% de tu límite de uso internacional para este ciclo de facturación.\n\n"
            "Uso actual: {current_usage}\n"
            "Tu límite: {threshold}\n"
            "El ciclo de facturación termina: {billing_cycle_end}\n\n"
            "Para evitar cargos por excedente, considera estas opciones:\n"
            "- Comprar un Pase Internacional: {buy_pass_url}\n"
            "- Cambiar de plan: {change_plan_url}\n\n"
            "Ver tu uso detallado: {usage_url}\n\n"
            "Gracias por ser un cliente valioso.\n\n"
            "Saludos cordiales,\n"
            "Tu Equipo Móvil"
        ),
        "email_50_percent_html": (
            """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Alerta de Uso Internacional</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #667eea;">Alerta de Uso Internacional</h1>
    <p>Hola {first_name},</p>
    <p><strong>Has usado el {percentage}% de tu límite de uso internacional.</strong></p>
    <p>Uso actual: {current_usage} | Límite: {threshold}</p>
    <p>El ciclo de facturación termina: {billing_cycle_end}</p>
    <p>Acciones recomendadas:</p>
    <ul>
        <li><a href="{buy_pass_url}">Comprar un Pase Internacional</a></li>
        <li><a href="{change_plan_url}">Cambiar de plan</a></li>
    </ul>
    <p><a href="{usage_url}">Ver uso detallado</a></p>
    <p>Saludos cordiales,<br>Tu Equipo Móvil</p>
</body>
</html>"""
        ),
        "push_50_percent_title": "Alerta de Uso Internacional",
        "push_50_percent_body": (
            "{first_name}, has usado {percentage}% de tu límite internacional ({current_usage}). "
            "Toca para ver opciones."
        ),
    },

    "fr_CA": {
        "sms_50_percent_body": (
            "{first_name}, vous avez utilisé {percentage}% de votre limite internationale "
            "({current_usage} sur {threshold}). Détails: {usage_url}"
        ),
        "email_50_percent_subject": (
            "Vous avez atteint {percentage}% de votre limite d'utilisation internationale"
        ),
        "email_50_percent_body": (
            "Bonjour {first_name},\n\n"
            "Vous avez utilisé {percentage}% de votre limite d'utilisation internationale pour ce cycle de facturation.\n\n"
            "Utilisation actuelle: {current_usage}\n"
            "Votre limite: {threshold}\n"
            "Fin du cycle de facturation: {billing_cycle_end}\n\n"
            "Pour éviter des frais supplémentaires, considérez ces options:\n"
            "- Acheter un Forfait International: {buy_pass_url}\n"
            "- Modifier votre forfait: {change_plan_url}\n\n"
            "Voir votre utilisation détaillée: {usage_url}\n\n"
            "Merci d'être un client fidèle.\n\n"
            "Cordialement,\n"
            "Votre Équipe Mobile"
        ),
        "email_50_percent_html": (
            """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Alerte d'Utilisation Internationale</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #667eea;">Alerte d'Utilisation Internationale</h1>
    <p>Bonjour {first_name},</p>
    <p><strong>Vous avez utilisé {percentage}% de votre limite d'utilisation internationale.</strong></p>
    <p>Utilisation actuelle: {current_usage} | Limite: {threshold}</p>
    <p>Fin du cycle: {billing_cycle_end}</p>
    <p>Actions recommandées:</p>
    <ul>
        <li><a href="{buy_pass_url}">Acheter un Forfait International</a></li>
        <li><a href="{change_plan_url}">Modifier votre forfait</a></li>
    </ul>
    <p><a href="{usage_url}">Voir utilisation détaillée</a></p>
    <p>Cordialement,<br>Votre Équipe Mobile</p>
</body>
</html>"""
        ),
        "push_50_percent_title": "Alerte Utilisation Internationale",
        "push_50_percent_body": (
            "{first_name}, vous avez utilisé {percentage}% de votre limite internationale ({current_usage}). "
            "Appuyez pour voir les options."
        ),
    },

    "de_DE": {
        "sms_50_percent_body": (
            "{first_name}, Sie haben {percentage}% Ihres internationalen Limits genutzt "
            "({current_usage} von {threshold}). Details: {usage_url}"
        ),
        "email_50_percent_subject": (
            "Sie haben {percentage}% Ihres internationalen Nutzungslimits erreicht"
        ),
        "email_50_percent_body": (
            "Hallo {first_name},\n\n"
            "Sie haben {percentage}% Ihres internationalen Nutzungslimits für diesen Abrechnungszeitraum genutzt.\n\n"
            "Aktuelle Nutzung: {current_usage}\n"
            "Ihr Limit: {threshold}\n"
            "Abrechnungszeitraum endet: {billing_cycle_end}\n\n"
            "Um zusätzliche Gebühren zu vermeiden, erwägen Sie diese Optionen:\n"
            "- Internationalen Pass kaufen: {buy_pass_url}\n"
            "- Tarif wechseln: {change_plan_url}\n\n"
            "Detaillierte Nutzung anzeigen: {usage_url}\n\n"
            "Vielen Dank für Ihre Treue.\n\n"
            "Mit freundlichen Grüßen,\n"
            "Ihr Mobile Team"
        ),
        "email_50_percent_html": (
            """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Internationale Nutzungswarnung</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #667eea;">Internationale Nutzungswarnung</h1>
    <p>Hallo {first_name},</p>
    <p><strong>Sie haben {percentage}% Ihres internationalen Nutzungslimits genutzt.</strong></p>
    <p>Aktuelle Nutzung: {current_usage} | Limit: {threshold}</p>
    <p>Abrechnungszeitraum endet: {billing_cycle_end}</p>
    <p>Empfohlene Aktionen:</p>
    <ul>
        <li><a href="{buy_pass_url}">Internationalen Pass kaufen</a></li>
        <li><a href="{change_plan_url}">Tarif wechseln</a></li>
    </ul>
    <p><a href="{usage_url}">Detaillierte Nutzung anzeigen</a></p>
    <p>Mit freundlichen Grüßen,<br>Ihr Mobile Team</p>
</body>
</html>"""
        ),
        "push_50_percent_title": "Internationale Nutzungswarnung",
        "push_50_percent_body": (
            "{first_name}, Sie haben {percentage}% Ihres internationalen Limits genutzt ({current_usage}). "
            "Tippen für Optionen."
        ),
    },

    "pt_BR": {
        "sms_50_percent_body": (
            "{first_name}, você usou {percentage}% do seu limite internacional "
            "({current_usage} de {threshold}). Detalhes: {usage_url}"
        ),
        "email_50_percent_subject": (
            "Você atingiu {percentage}% do seu limite de uso internacional"
        ),
        "email_50_percent_body": (
            "Olá {first_name},\n\n"
            "Você usou {percentage}% do seu limite de uso internacional neste ciclo de faturamento.\n\n"
            "Uso atual: {current_usage}\n"
            "Seu limite: {threshold}\n"
            "Ciclo de faturamento termina em: {billing_cycle_end}\n\n"
            "Para evitar cobranças adicionais, considere estas opções:\n"
            "- Comprar um Pacote Internacional: {buy_pass_url}\n"
            "- Mudar de plano: {change_plan_url}\n\n"
            "Ver seu uso detalhado: {usage_url}\n\n"
            "Obrigado por ser um cliente valioso.\n\n"
            "Atenciosamente,\n"
            "Sua Equipe Mobile"
        ),
        "email_50_percent_html": (
            """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Alerta de Uso Internacional</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #667eea;">Alerta de Uso Internacional</h1>
    <p>Olá {first_name},</p>
    <p><strong>Você usou {percentage}% do seu limite de uso internacional.</strong></p>
    <p>Uso atual: {current_usage} | Limite: {threshold}</p>
    <p>Ciclo de faturamento termina em: {billing_cycle_end}</p>
    <p>Ações recomendadas:</p>
    <ul>
        <li><a href="{buy_pass_url}">Comprar um Pacote Internacional</a></li>
        <li><a href="{change_plan_url}">Mudar de plano</a></li>
    </ul>
    <p><a href="{usage_url}">Ver uso detalhado</a></p>
    <p>Atenciosamente,<br>Sua Equipe Mobile</p>
</body>
</html>"""
        ),
        "push_50_percent_title": "Alerta de Uso Internacional",
        "push_50_percent_body": (
            "{first_name}, você usou {percentage}% do seu limite internacional ({current_usage}). "
            "Toque para ver opções."
        ),
    },
}

# Default fallback locale
DEFAULT_LOCALE = "en_US"


def get_localized_strings(locale: str) -> Dict[str, str]:
    """
    Get localized strings for a specific locale.

    Falls back to DEFAULT_LOCALE if the requested locale is not available.

    Args:
        locale: Locale code (e.g., "en_US", "es_MX")

    Returns:
        Dictionary of localized strings for the specified locale
    """
    if locale in LOCALIZED_STRINGS:
        return LOCALIZED_STRINGS[locale]

    # Try language-only fallback (e.g., "es" from "es_AR")
    language = locale.split("_")[0]
    for key in LOCALIZED_STRINGS:
        if key.startswith(language + "_"):
            return LOCALIZED_STRINGS[key]

    return LOCALIZED_STRINGS[DEFAULT_LOCALE]


def get_supported_locales() -> list:
    """
    Get list of all supported locales.

    Returns:
        List of supported locale codes
    """
    return list(LOCALIZED_STRINGS.keys())


def is_locale_supported(locale: str) -> bool:
    """
    Check if a locale is directly supported.

    Args:
        locale: Locale code to check

    Returns:
        True if locale is directly supported, False otherwise
    """
    return locale in LOCALIZED_STRINGS
