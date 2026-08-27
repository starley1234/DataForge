import sys
import argparse
import pandas as pd
from rich.console import Console
from rich.table import Table
from engine import EnrichmentEngine
from company_sources import MockCompanyRegistry
from email_generator import generate_email_permutations
from validator import verify_email_full, normalize_phone

console = Console()


def print_table_leads(leads):
    table = Table(title="[bold green]База данных ЛПР и контактов предприятий России[/bold green]")
    table.add_column("ИНН", style="cyan", no_wrap=True)
    table.add_column("Компания", style="bold white")
    table.add_column("ФИО ЛПР", style="magenta")
    table.add_column("Должность", style="yellow")
    table.add_column("Email ЛПР", style="green")
    table.add_column("Статус Email", style="blue")
    table.add_column("Телефон", style="cyan")
    table.add_column("URL / Профиль", style="dim")
    table.add_column("Скоринг", justify="right", style="bold")

    for l in leads:
        table.add_row(
            l["inn"],
            l["company_name"][:25],
            l["dm_full_name"],
            l["dm_title"][:25] if l["dm_title"] else "",
            l["dm_email"] or "-",
            l["email_status"] or "-",
            l["dm_phone"] or "-",
            l["dm_profile_url"] or l["website"] or "-",
            f"{l['confidence_score']}%"
        )

    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="B2B Lead Enrichment Engine (Россия/СНГ)")
    parser.add_argument("--demo", action="store_true", help="Запустить демонстрационный сбор и обогащение")
    parser.add_argument("--inn", type=str, help="ИНН компании для поиска и обогащения")
    parser.add_argument("--export-csv", type=str, help="Путь для экспорта в CSV (например leads.csv)")
    parser.add_argument("--export-excel", type=str, help="Путь для экспорта в Excel (например leads.xlsx)")
    parser.add_argument("--generate-email", nargs=2, metavar=('NAME', 'DOMAIN'), help="Сгенерировать варианты email по ФИО и домену")
    parser.add_argument("--check-email", type=str, help="Проверить MX и валидность email")
    parser.add_argument("--check-phone", type=str, help="Проверить и нормализовать номер телефона")

    args = parser.parse_args()
    engine = EnrichmentEngine()

    if args.generate_email:
        name, domain = args.generate_email
        console.print(f"[bold yellow]Генерация корпоративных адресов для:[/bold yellow] {name} @ {domain}")
        perms = generate_email_permutations(name, domain)
        t = Table(title=f"Шаблоны email: {name}")
        t.add_column("Email", style="green")
        t.add_column("Паттерн", style="cyan")
        t.add_column("Вероятность", style="bold")
        for p in perms:
            t.add_row(p["email"], p["pattern"], f"{p['confidence']}%")
        console.print(t)
        return

    if args.check_email:
        res = verify_email_full(args.check_email)
        console.print(f"[bold]Результат проверки email {args.check_email}:[/bold]")
        console.print(res)
        return

    if args.check_phone:
        res = normalize_phone(args.check_phone)
        console.print(f"[bold]Результат валидации телефона {args.check_phone}:[/bold]")
        console.print(res)
        return

    if args.demo:
        console.print("[bold blue]Запуск демонстрационного пайплайна сбора и обогащения базы...[/bold blue]")
        mock_data = engine.mock_registry.get_all()
        for comp in mock_data:
            engine.enrich_company_and_dms(comp, scrape_web=False, verify_emails=True)

        leads = engine.get_all_leads()
        print_table_leads(leads)

        if args.export_csv:
            df = pd.DataFrame(leads)
            df.to_csv(args.export_csv, index=False, encoding="utf-8-sig")
            console.print(f"[bold green]Успешно экспортировано в {args.export_csv}[/bold green]")

        if args.export_excel:
            df = pd.DataFrame(leads)
            df.to_excel(args.export_excel, index=False)
            console.print(f"[bold green]Успешно экспортировано в {args.export_excel}[/bold green]")
        return

    if args.inn:
        comp = engine.fetch_and_enrich_by_inn(args.inn, scrape_web=True, verify_emails=True)
        if comp:
            leads = engine.get_all_leads()
            filtered = [l for l in leads if l["inn"] == args.inn]
            print_table_leads(filtered)
            if args.export_csv:
                df = pd.DataFrame(filtered)
                df.to_csv(args.export_csv, index=False, encoding="utf-8-sig")
            if args.export_excel:
                df = pd.DataFrame(filtered)
                df.to_excel(args.export_excel, index=False)
        else:
            console.print(f"[red]Компания с ИНН {args.inn} не найдена в официальных реестрах.[/red]")
        return

    # Если без аргументов - показываем текущую БД
    leads = engine.get_all_leads()
    if leads:
        print_table_leads(leads)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
