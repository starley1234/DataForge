import sys
import argparse
import uvicorn
from typing import Optional
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track, Progress, SpinnerColumn, TextColumn, BarColumn

from engine import EnrichmentEngine
from email_generator import generate_email_permutations
from validator import verify_email_full, normalize_phone
from deliverability import analyze_domain_deliverability
from exporter import (
    export_to_csv, export_to_excel, export_to_amocrm_csv,
    export_to_bitrix24_csv, export_to_hubspot_csv, export_to_vcard,
    generate_outreach_email, generate_cold_calling_script
)
from batch_processor import BatchProcessor
from config import settings

console = Console()


def print_table_leads(leads, title="База данных ЛПР и контактов предприятий России"):
    table = Table(title=f"[bold green]{title}[/bold green]", show_lines=True)
    table.add_column("ID", style="dim", justify="right", width=4)
    table.add_column("ИНН", style="cyan", no_wrap=True)
    table.add_column("Организация", style="bold white")
    table.add_column("ФИО ЛПР", style="magenta")
    table.add_column("Должность / Роль", style="yellow")
    table.add_column("Email", style="green")
    table.add_column("Статус Email", style="blue")
    table.add_column("Телефон / Время", style="cyan")
    table.add_column("Регион", style="dim")
    table.add_column("Скоринг", justify="right", style="bold")

    for l in leads:
        lead_id = str(l.get("id", "-"))
        inn = l.get("inn", "-")
        comp = l.get("company_name", "-")
        name = l.get("dm_full_name", "-")
        title_role = f"{l.get('dm_title', '')}\n[dim]({l.get('dm_role_level', 'C-Level')})[/dim]"
        email = l.get("dm_email") or "-"
        estatus = l.get("email_status") or "-"
        phone = l.get("dm_phone") or "-"
        tz = l.get("phone_timezone") or "MSK"
        phone_display = f"{phone}\n[dim]{tz}[/dim]" if phone != "-" else "-"
        reg = l.get("region") or "-"
        score = f"{l.get('confidence_score', 50)}%"

        table.add_row(
            lead_id,
            inn,
            comp[:28],
            name,
            title_role,
            email,
            estatus,
            phone_display,
            reg[:18],
            score
        )

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="B2B Lead Enrichment Engine (Enterprise Edition) — Комплексный поиск, скоринг и валидация ЛПР РФ",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # Режимы работы
    parser.add_argument("--demo", action="store_true", help="Запустить сбор и обогащение эталонной корпоративной базы")
    parser.add_argument("--query", type=str, help="ИНН, ОГРН или наименование организации для поиска и обогащения")
    parser.add_argument("--inn", type=str, help="ИНН компании для прямого поиска")
    parser.add_argument("--domain", type=str, help="Домен организации для краулинга контактов и реквизитов")
    parser.add_argument("--batch", type=str, help="Путь к файлу CSV или Excel со списком ИНН для пакетной обработки")
    parser.add_argument("--list", action="store_true", help="Показать сохраненные контакты из базы данных")
    parser.add_argument("--stats", action="store_true", help="Отобразить сводную аналитику базы данных")
    
    # Инструменты
    parser.add_argument("--generate-email", nargs=2, metavar=('ФИО', 'ДОМЕН'), help="Сгенерировать корпоративные шаблоны email")
    parser.add_argument("--check-email", type=str, help="Проверить MX DNS, синтаксис и доступность email")
    parser.add_argument("--check-phone", type=str, help="Проверить телефон (E.164, оператор, часовой пояс, окно звонка)")
    parser.add_argument("--deliverability", type=str, help="Аудит доставляемости домена (MX, SPF, DMARC, DKIM, RBL)")
    parser.add_argument("--outreach", type=int, metavar="LEAD_ID", help="Сгенерировать B2B холодное письмо для ЛПР по ID")
    parser.add_argument("--call-script", type=int, metavar="LEAD_ID", help="Сгенерировать скрипт холодного звонка для ЛПР по ID")
    parser.add_argument("--reverify", action="store_true", help="Повторно проверить все MX DNS записи в базе")

    # Экспорт
    parser.add_argument("--export-csv", type=str, help="Экспорт текущей базы в CSV (UTF-8 с BOM)")
    parser.add_argument("--export-excel", type=str, help="Экспорт текущей базы в стилизованный Excel (.xlsx)")
    parser.add_argument("--export-amocrm", type=str, help="Экспорт в CSV для amoCRM")
    parser.add_argument("--export-bitrix24", type=str, help="Экспорт в CSV для Битрикс24")
    parser.add_argument("--export-hubspot", type=str, help="Экспорт в CSV для HubSpot / Salesforce")
    parser.add_argument("--export-vcard", type=str, help="Экспорт базы в формат vCard (.vcf)")

    # Запуск сервера
    parser.add_argument("--serve", action="store_true", help="Запустить Web-сервер и UI панель управления")
    parser.add_argument("--host", type=str, default=settings.HOST, help=f"Хост веб-сервера (по умолчанию {settings.HOST})")
    parser.add_argument("--port", type=int, default=settings.PORT, help=f"Порт веб-сервера (по умолчанию {settings.PORT})")

    args = parser.parse_args()
    engine = EnrichmentEngine()

    if args.serve:
        console.print(f"[bold green]Запуск веб-сервера B2B Lead Enrichment Engine на {args.host}:{args.port}...[/bold green]")
        uvicorn.run("web_app:app", host=args.host, port=args.port, reload=False)
        return

    if args.stats:
        s = engine.get_dashboard_stats()
        console.print("\n[bold cyan]═══ Сводная аналитика базы данных ═══[/bold cyan]")
        console.print(f"Предприятий в базе: [bold green]{s['total_companies']}[/bold green]")
        console.print(f"Контактов ЛПР: [bold green]{s['total_dms']}[/bold green]")
        console.print(f"Email с активным MX: [bold green]{s['valid_emails_count']}[/bold green]")
        console.print(f"Email по корпоративному паттерну: [bold yellow]{s['generated_emails_count']}[/bold yellow]")
        console.print(f"Прямых мобильных номеров: [bold green]{s['mobile_phones_count']}[/bold green]")
        console.print(f"Офисных номеров / приемных: [bold cyan]{s['office_phones_count']}[/bold cyan]")
        console.print("\n[bold]Распределение по уровням ЛПР:[/bold]")
        for role, cnt in s['roles_breakdown'].items():
            console.print(f"  • {role}: {cnt}")
        return

    if args.generate_email:
        name, domain = args.generate_email
        console.print(f"[bold yellow]Генерация корпоративных адресов для:[/bold yellow] [bold white]{name}[/bold white] @ [cyan]{domain}[/cyan]")
        perms = generate_email_permutations(name, domain)
        t = Table(title=f"Корпоративные шаблоны: {name}", show_lines=True)
        t.add_column("Email", style="green")
        t.add_column("Паттерн", style="cyan")
        t.add_column("Вероятность", justify="right", style="bold")
        for p in perms:
            t.add_row(p["email"], p["pattern"], f"{p['confidence']}%")
        console.print(t)
        return

    if args.check_email:
        res = verify_email_full(args.check_email)
        console.print(f"\n[bold]Результат валидации email [green]{args.check_email}[/green]:[/bold]")
        for k, v in res.items():
            console.print(f"  [cyan]{k}[/cyan]: {v}")
        return

    if args.check_phone:
        res = normalize_phone(args.check_phone)
        console.print(f"\n[bold]Результат валидации телефона [green]{args.check_phone}[/green]:[/bold]")
        for k, v in res.items():
            console.print(f"  [cyan]{k}[/cyan]: {v}")
        return

    if args.deliverability:
        res = analyze_domain_deliverability(args.deliverability)
        console.print(Panel(
            f"[bold]Домен:[/bold] {res['domain']}\n"
            f"[bold]Провайдер:[/bold] {res['provider']}\n"
            f"[bold]MX Хост:[/bold] {res['mx_host']}\n"
            f"[bold]SPF:[/bold] {res['spf_qualifier']} ({res['has_spf']})\n"
            f"[bold]DMARC:[/bold] {res['dmarc_policy']} ({res['has_dmarc']})\n"
            f"[bold]Deliverability Score:[/bold] [bold green]{res['deliverability_score']}/100[/bold green]",
            title="[bold cyan]Аудит доставляемости домена[/bold cyan]"
        ))
        return

    if args.outreach:
        lead = engine.get_lead_by_id(args.outreach)
        if not lead:
            console.print(f"[red]Лид с ID {args.outreach} не найден в базе.[/red]")
            return
        draft = generate_outreach_email(lead, "partnership")
        console.print(f"\n[bold green]═══ Шаблон холодного письма для {lead['dm_full_name']} ═══[/bold green]")
        console.print(f"[bold cyan]Тема:[/bold cyan] {draft['subject']}")
        console.print(f"[bold cyan]Получатель:[/bold cyan] {draft['recipient_email']}")
        console.print("\n" + draft["body"])
        return

    if args.call_script:
        lead = engine.get_lead_by_id(args.call_script)
        if not lead:
            console.print(f"[red]Лид с ID {args.call_script} не найден в базе.[/red]")
            return
        script = generate_cold_calling_script(lead)
        console.print(f"\n[bold green]═══ Скрипт холодного звонка: {lead['dm_full_name']} ({lead['company_name']}) ═══[/bold green]")
        console.print(f"[bold yellow]1. Секретарский барьер:[/bold yellow]\n{script['gatekeeper_script']}\n")
        console.print(f"[bold yellow]2. Открытие разговора с ЛПР (30-сек Hook):[/bold yellow]\n{script['intro_pitch']}\n")
        console.print(f"[bold yellow]3. Закрытие на встречу:[/bold yellow]\n{script['closing']}\n")
        return

    if args.reverify:
        console.print("[bold yellow]Запуск повторной MX-проверки всех email в базе...[/bold yellow]")
        cnt = engine.reverify_all_emails()
        console.print(f"[bold green]Успешно перепроверено {cnt} контактов.[/bold green]")
        return

    if args.demo:
        console.print("[bold blue]Запуск сбора и обогащения эталонной базы компаний РФ...[/bold blue]")
        mock_data = engine.mock_registry.get_all()
        for comp in track(mock_data, description="Обогащение предприятий..."):
            engine.enrich_company_and_dms(comp, scrape_web=False, verify_emails=True)

        leads = engine.get_all_leads()
        print_table_leads(leads)

        if args.export_csv:
            export_to_csv(leads, args.export_csv)
            console.print(f"[bold green]Экспорт в {args.export_csv}[/bold green]")
        if args.export_excel:
            export_to_excel(leads, args.export_excel)
            console.print(f"[bold green]Экспорт в {args.export_excel}[/bold green]")
        if args.export_vcard:
            export_to_vcard(leads, args.export_vcard)
            console.print(f"[bold green]Экспорт в {args.export_vcard}[/bold green]")
        return

    if args.batch:
        console.print(f"[bold blue]Загрузка файла для пакетного обогащения: {args.batch}[/bold blue]")
        try:
            with open(args.batch, "rb") as f:
                content = f.read()
            bp = BatchProcessor(engine)
            items = bp.parse_file_to_items(content, args.batch)
            console.print(f"[green]Обнаружено записей для обработки: {len(items)}[/green]")
            task_id = bp.start_batch_enrichment(items)
            console.print(f"[bold green]Задача пакетного обогащения запущена: ID = {task_id}[/bold green]")
        except Exception as e:
            console.print(f"[red]Ошибка чтения файла {args.batch}: {e}[/red]")
        return

    search_q = args.query or args.inn
    if search_q:
        console.print(f"[bold blue]Поиск и обогащение организации: {search_q}...[/bold blue]")
        comp = engine.fetch_and_enrich(search_q, scrape_web=True, verify_emails=True)
        if comp:
            leads = engine.get_all_leads(query=comp.inn)
            print_table_leads(leads, title=f"Найдено: {comp.name}")
        else:
            console.print(f"[red]Организация '{search_q}' не найдена в реестрах.[/red]")
        return

    if args.domain:
        console.print(f"[bold blue]Сбор данных по сайту: {args.domain}...[/bold blue]")
        comp = engine.enrich_by_domain(args.domain, verify_emails=True)
        if comp:
            leads = engine.get_all_leads(query=comp.inn)
            print_table_leads(leads, title=f"Обогащено по домену: {args.domain}")
        return

    if args.list:
        leads = engine.get_all_leads()
        if leads:
            print_table_leads(leads)
        else:
            console.print("[yellow]База данных пуста. Запустите --demo или укажите --inn для наполнения.[/yellow]")
        return

    # Экспорт текущей базы без других команд
    if args.export_csv or args.export_excel or args.export_amocrm or args.export_bitrix24 or args.export_hubspot or args.export_vcard:
        leads = engine.get_all_leads()
        if args.export_csv:
            export_to_csv(leads, args.export_csv)
            console.print(f"[bold green]Экспорт в CSV: {args.export_csv}[/bold green]")
        if args.export_excel:
            export_to_excel(leads, args.export_excel)
            console.print(f"[bold green]Экспорт в Excel: {args.export_excel}[/bold green]")
        if args.export_amocrm:
            export_to_amocrm_csv(leads, args.export_amocrm)
            console.print(f"[bold green]Экспорт в amoCRM: {args.export_amocrm}[/bold green]")
        if args.export_bitrix24:
            export_to_bitrix24_csv(leads, args.export_bitrix24)
            console.print(f"[bold green]Экспорт в Битрикс24: {args.export_bitrix24}[/bold green]")
        if args.export_hubspot:
            export_to_hubspot_csv(leads, args.export_hubspot)
            console.print(f"[bold green]Экспорт в HubSpot: {args.export_hubspot}[/bold green]")
        if args.export_vcard:
            export_to_vcard(leads, args.export_vcard)
            console.print(f"[bold green]Экспорт в vCard: {args.export_vcard}[/bold green]")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
