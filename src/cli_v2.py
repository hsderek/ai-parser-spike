#!/usr/bin/env python3
"""
FastAPI-ready CLI interface using service layer
Demonstrates clean separation between CLI and API logic
"""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.json import JSON
from rich.panel import Panel
import json
import asyncio

from .api_models import ParseRequest, IterativeParseRequest
from .api_routes import VRLParserRoutes
from .config import Config
from .logging_config import setup_logging, get_logger

app = typer.Typer(help="AI-powered VRL parser generator (FastAPI-ready)")
console = Console()


@app.command()
def parse(
    input_file: Path = typer.Argument(..., help="NDJSON input file to analyze"),
    output_dir: Path = typer.Option("./output", "--output", "-o", help="Output directory"),
    level: str = typer.Option("medium", "--level", "-l", help="Parsing level: high, medium, low"),
    domains: Optional[str] = typer.Option(None, "--domains", "-d", help="Comma-separated domains: cyber,travel,iot,defence,financial"),
    model: str = typer.Option("opus", "--model", "-m", help="LLM model preference: opus, sonnet, auto"),
    max_fields: Optional[int] = typer.Option(None, "--max-fields", help="Maximum fields to extract"),
    iterative: bool = typer.Option(False, "--iterative", "-i", help="Use iterative refinement"),
    max_iterations: int = typer.Option(3, "--iterations", help="Max refinement iterations (iterative mode)"),
    target_tier: int = typer.Option(2, "--target-tier", help="Target performance tier (iterative mode)"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON only (no rich formatting)"),
    validate_only: bool = typer.Option(False, "--validate", help="Only validate file format")
) -> None:
    """Generate VRL parser from NDJSON log files"""
    
    # Initialize configuration and logging
    config = Config(llm_model_preference=model)
    
    # Setup logging based on config
    setup_logging(
        log_level=config.log_level,
        log_to_file=config.log_to_file,
        log_to_console=config.log_to_console,
        logs_dir=config.logs_dir,
        app_name="ai_parser_cli",
        structured_logging=config.structured_logging,
        debug_mode=config.debug_mode
    )
    
    logger = get_logger("CLI")
    logger.info(f"Starting CLI with input file: {input_file}")
    
    # Initialize routes
    routes = VRLParserRoutes(config)
    
    # File validation
    if validate_only:
        asyncio.run(validate_file_command(routes, input_file, json_output))
        return
    
    # Parse domains
    domain_list = [d.strip() for d in domains.split(",")] if domains else None
    
    if json_output:
        # JSON-only output for API-like behavior
        asyncio.run(parse_json_output(routes, input_file, level, domain_list, model, max_fields, iterative, max_iterations, target_tier))
    else:
        # Rich CLI output
        asyncio.run(parse_rich_output(routes, input_file, output_dir, level, domain_list, model, max_fields, iterative, max_iterations, target_tier))


async def validate_file_command(routes: VRLParserRoutes, input_file: Path, json_output: bool):
    """Handle file validation command"""
    try:
        result = await routes.validate_file(str(input_file))
        
        if json_output:
            print(json.dumps(result, indent=2))
        else:
            display_validation_results(result)
            
    except Exception as e:
        error_result = {"status": "error", "message": str(e)}
        if json_output:
            print(json.dumps(error_result, indent=2))
        else:
            console.print(f"[red]Validation Error: {e}[/red]")
        raise typer.Exit(1)


async def parse_json_output(routes, input_file, level, domains, model, max_fields, iterative, max_iterations, target_tier):
    """Handle JSON-only output (API-like behavior)"""
    try:
        if iterative:
            request = IterativeParseRequest(
                file_path=str(input_file),
                level=level,
                domains=domains,
                max_fields=max_fields,
                model_preference=model,
                max_iterations=max_iterations,
                target_performance_tier=target_tier
            )
            result = await routes.parse_logs_iterative(request)
        else:
            request = ParseRequest(
                file_path=str(input_file),
                level=level,
                domains=domains,
                max_fields=max_fields,
                model_preference=model
            )
            result = await routes.parse_logs(request)
        
        # Output pure JSON (API response format)
        print(json.dumps(result.dict(), indent=2))
        
    except Exception as e:
        error_result = {"status": "error", "message": str(e)}
        print(json.dumps(error_result, indent=2))
        raise typer.Exit(1)


async def parse_rich_output(routes, input_file, output_dir, level, domains, model, max_fields, iterative, max_iterations, target_tier):
    """Handle rich CLI output with progress bars and tables"""
    
    console.print(f"[blue]🔍 Analyzing NDJSON file: {input_file}[/blue]")
    console.print(f"[blue]📁 Output directory: {output_dir}[/blue]")
    console.print(f"[blue]⚙️  Parsing level: {level}[/blue]")
    
    if domains:
        console.print(f"[blue]🎯 Target domains: {', '.join(domains)}[/blue]")
    
    if iterative:
        console.print(f"[blue]🔄 Iterative mode: {max_iterations} iterations, target tier {target_tier}[/blue]")
    
    output_dir.mkdir(exist_ok=True)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        
        try:
            if iterative:
                task = progress.add_task("Running iterative parser generation...", total=None)
                
                request = IterativeParseRequest(
                    file_path=str(input_file),
                    level=level,
                    domains=domains,
                    max_fields=max_fields,
                    model_preference=model,
                    max_iterations=max_iterations,
                    target_performance_tier=target_tier
                )
                result = await routes.parse_logs_iterative(request)
                
            else:
                task = progress.add_task("Generating VRL parser...", total=None)
                
                request = ParseRequest(
                    file_path=str(input_file),
                    level=level,
                    domains=domains,
                    max_fields=max_fields,
                    model_preference=model
                )
                result = await routes.parse_logs(request)
            
            progress.update(task, description="Saving results...")
            
            # Save files
            vrl_file = output_dir / "parser.vrl"
            fields_file = output_dir / "fields.json"
            
            vrl_file.write_text(result.data["vrl_code"])
            fields_file.write_text(json.dumps(result.dict(), indent=2))
            
            progress.update(task, description="Complete!")
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    # Display results
    display_parse_results(result, output_dir, iterative)


def display_parse_results(result, output_dir: Path, iterative: bool):
    """Display rich formatted results"""
    console.print(f"\n[green]✓ VRL parser generated successfully![/green]")
    console.print(f"[blue]📁 Files saved to: {output_dir}[/blue]")
    
    # Fields table
    fields_data = result.data.get("fields", [])
    if fields_data:
        table = Table(title="Extracted Fields")
        table.add_column("Field", style="cyan")
        table.add_column("Type", style="green") 
        table.add_column("CPU Cost", style="yellow")
        table.add_column("Confidence", style="magenta")
        table.add_column("High Value", style="red")
        
        for field in fields_data[:10]:  # Show first 10 fields
            table.add_row(
                field["name"],
                field["type"],
                field["cpu_cost"],
                f"{field['confidence']:.2f}",
                "✓" if field["is_high_value"] else ""
            )
        
        if len(fields_data) > 10:
            table.add_row("...", f"+{len(fields_data) - 10} more fields", "", "", "")
        
        console.print(table)
    
    # Parser source attribution
    parser_source = result.data.get("parser_source")
    if parser_source:
        source_panel = Panel(
            f"Type: {parser_source['type']}\n"
            f"Sources: {', '.join(parser_source['sources'][:3])}{'...' if len(parser_source['sources']) > 3 else ''}\n"
            f"Confidence: {parser_source['confidence']:.2f}\n"
            f"Description: {parser_source['description']}",
            title="🔗 Parser Source Attribution",
            border_style="blue"
        )
        console.print(source_panel)
    
    # Summary
    summary = result.data.get("summary", {})
    summary_text = f"""
📊 Summary:
• Total Fields: {summary.get('total_fields', 0)}
• High-Value Fields: {summary.get('high_value_fields', 0)}
• Low CPU Cost: {summary.get('low_cpu_cost_fields', 0)}
• Processing Time: {summary.get('total_processing_time_seconds', 0):.2f}s
"""
    
    if iterative and hasattr(result, 'iterations'):
        summary_text += f"""
🔄 Iterative Results:
• Total Iterations: {result.iterations['total_iterations']}
• Performance Improvement: {result.iterations['performance_improvement']}
• Final Tier: {result.data['final_performance_tier']}
• Target Achieved: {'✓' if result.iterations['target_tier_achieved'] else '✗'}
"""
    
    console.print(Panel(summary_text, title="📋 Results Summary", border_style="green"))
    
    # LLM usage
    llm_usage = result.data.get("llm_usage")
    if llm_usage:
        console.print(f"\n[dim]💰 LLM Cost: ${llm_usage['estimated_cost_usd']:.4f} ({llm_usage['total_tokens']} tokens)[/dim]")


def display_validation_results(result):
    """Display file validation results"""
    data = result.get("data", {})
    status = result.get("status", "unknown")
    
    if status == "success":
        console.print("[green]✓ File validation successful[/green]")
    elif status == "warning":
        console.print("[yellow]⚠ File validation completed with warnings[/yellow]")
    else:
        console.print("[red]✗ File validation failed[/red]")
    
    # Validation details table
    table = Table(title="File Validation Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("File Path", data.get("file_path", ""))
    table.add_row("Total Lines", str(data.get("total_lines", 0)))
    table.add_row("Valid JSON Lines", str(data.get("valid_json_lines", 0)))
    table.add_row("Validity Ratio", f"{data.get('validity_ratio', 0):.2%}")
    table.add_row("Sample Fields", str(len(data.get("sample_fields", []))))
    table.add_row("Parseable", "✓" if data.get("estimated_parseable", False) else "✗")
    
    console.print(table)
    
    # Recommendations
    recommendations = data.get("recommendations", [])
    if recommendations:
        rec_text = "\n".join(f"• {rec}" for rec in recommendations)
        console.print(Panel(rec_text, title="💡 Recommendations", border_style="yellow"))


@app.command()
def health():
    """Check system health and service availability"""
    config = Config()
    routes = VRLParserRoutes(config)
    
    try:
        result = asyncio.run(routes.health_check())
        
        console.print(f"\n[green]System Health: {result.status.upper()}[/green]")
        console.print(f"[blue]Timestamp: {result.timestamp}[/blue]")
        console.print(f"[blue]Version: {result.version}[/blue]")
        
        # Services table
        table = Table(title="Service Status")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        
        for service, status in result.services.items():
            color = "green" if status in ["connected", "available", "active"] else "red"
            table.add_row(service, f"[{color}]{status}[/{color}]")
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Health check failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def formats():
    """Show supported formats and data sources"""
    config = Config()
    routes = VRLParserRoutes(config)
    
    try:
        result = asyncio.run(routes.get_supported_formats())
        data = result["data"]
        
        console.print("\n[green]📝 Supported File Formats:[/green]")
        for fmt in data["supported_formats"]:
            console.print(f"  • {fmt}")
        
        console.print("\n[green]🎯 Supported Domains:[/green]")
        for domain in data["supported_domains"]:
            console.print(f"  • {domain}")
        
        console.print("\n[green]⚙️  Parsing Levels:[/green]")
        for level in data["parsing_levels"]:
            console.print(f"  • {level}")
        
        console.print("\n[green]📊 Common Data Sources:[/green]")
        for source in data["common_data_sources"]:
            console.print(f"  • {source}")
            
    except Exception as e:
        console.print(f"[red]Error retrieving formats: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()