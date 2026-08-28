#!/usr/bin/env python3
"""
Скрипт комплексного аудита доставляемости почты и безопасности корпоративного домена.

Примеры использования:
    python3 scripts/audit_deliverability.py yandex.ru sberbank.ru
    python3 scripts/audit_deliverability.py ozon.ru --json
"""

import sys
import os
import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from core.deliverability import analyze_domain_deliverability

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Аудит доставляемости домена (MX, SPF, DMARC, DKIM, RBL)")
    parser.add_argument("domains", nargs="+", help="Один или несколько доменов для проверки")
    parser.add_argument("--json", action="store_true", help="Вывести результат в формате JSON")

    args = parser.parse_args()
    results = []

    for dom in args.domains:
        res = analyze_domain_deliverability(dom.strip())
        results.append(res)

        if not args.json:
            color = "green" if res.get("deliverability_score", 0) >= 70 else ("yellow" if res.get("deliverability_score", 0) >= 50 else "red")
            
            recs = "\n".join([f"  • {r}" for r in res.get("recommendations", [])]) or "  • Замечаний нет, домен отлично настроен."

            console.print(Panel(
                f"[bold]Домен:[/bold] [cyan]{res['domain']}[/cyan]\n"
                f"[bold]Почтовый сервис:[/bold] {res['provider']}\n"
                f"[bold]MX Хост:[/bold] {res['mx_host'] or 'Отсутствует'}\n"
                f"[bold]SPF Политика:[/bold] {res['spf_qualifier']} ({res['has_spf']})\n"
                f"[bold]DMARC Политика:[/bold] {res['dmarc_policy']} ({res['has_dmarc']})\n"
                f"[bold]DKIM Статус:[/bold] {'✓ Настроен (' + str(res.get('dkim_selector')) + ')' if res['has_dkim'] else '✗ Не обнаружен'}\n"
                f"[bold]Спам-базы (RBL):[/bold] {'✗ Обнаружен в списках: ' + ', '.join(res['rbl_status']['listings']) if res['rbl_status']['is_blacklisted'] else '✓ Чист'}\n\n"
                f"[bold]Индекс доставляемости (Score):[/bold] [bold {color}]{res['deliverability_score']}/100[/bold {color}]\n\n"
                f"[bold]Рекомендации:[/bold]\n{recs}",
                title=f"[bold {color}]Аудит доставляемости: {res['domain']}[/bold {color}]"
            ))

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
