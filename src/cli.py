import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import json

from .pipeline import VRLPipeline
from .config import Config

app = typer.Typer(help="AI-powered VRL parser generator")
console = Console()

@app.command()
def parse(
    input_file: Path = typer.Argument(..., help="NDJSON input file to analyze"),
    output_dir: Path = typer.Option("./output", "--output", "-o", help="Output directory"),
    level: str = typer.Option("medium", "--level", "-l", help="Parsing level: high, medium, low"),
    domains: Optional[str] = typer.Option(None, "--domains", "-d", help="Comma-separated domains: cyber,travel,iot,defence,financial"),
    model: str = typer.Option("opus", "--model", "-m", help="LLM model preference: opus, sonnet, auto")
) -> None:
    if not input_file.exists():
        console.print(f"[red]Error: Input file {input_file} does not exist[/red]")
        raise typer.Exit(1)
    
    if level not in ["high", "medium", "low"]:
        console.print("[red]Error: Level must be high, medium, or low[/red]")
        raise typer.Exit(1)
    
    config = Config(llm_model_preference=model)
    pipeline = VRLPipeline(config)
    
    console.print(f"[blue]Analyzing NDJSON file: {input_file}[/blue]")
    console.print(f"[blue]Output directory: {output_dir}[/blue]")
    console.print(f"[blue]Parsing level: {level}[/blue]")
    
    if domains:
        domain_list = [d.strip() for d in domains.split(",")]
        console.print(f"[blue]Target domains: {', '.join(domain_list)}[/blue]")
    else:
        domain_list = None
    
    output_dir.mkdir(exist_ok=True)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=None)
        
        try:
            result = pipeline.process(input_file, level, domain_list)
            
            progress.update(task, description="Saving results...")
            
            vrl_file = output_dir / "parser.vrl"
            fields_file = output_dir / "fields.json"
            
            vrl_file.write_text(result.vrl_code)
            
            # Create FastAPI-style response structure
            api_response = {
                "status": "success",
                "message": f"Successfully generated VRL parser with {len(result.fields)} fields",
                "data": {
                    "vrl_code": result.vrl_code,
                    "fields": [field.model_dump() for field in result.fields],
                    "data_source": result.data_source.model_dump() if result.data_source else None,
                    "performance_metrics": result.performance_metrics,
                    "llm_usage": result.llm_usage.model_dump() if result.llm_usage else None,
                    "parser_source": result.parser_source.model_dump() if result.parser_source else None,
                    "summary": {
                        "total_fields": len(result.fields),
                        "high_value_fields": sum(1 for f in result.fields if f.is_high_value),
                        "low_cpu_cost_fields": sum(1 for f in result.fields if f.cpu_cost.value == "low"),
                        "medium_cpu_cost_fields": sum(1 for f in result.fields if f.cpu_cost.value == "medium"),
                        "high_cpu_cost_fields": sum(1 for f in result.fields if f.cpu_cost.value == "high")
                    }
                }
            }
            
            fields_file.write_text(json.dumps(api_response, indent=2))
            
            progress.update(task, description="Complete!")
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    display_results(result, output_dir)

def display_results(result, output_dir: Path) -> None:
    console.print(f"\n[green]✓ VRL parser generated successfully![/green]")
    console.print(f"[blue]Files saved to: {output_dir}[/blue]")
    
    table = Table(title="Extracted Fields")
    table.add_column("Field", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("CPU Cost", style="yellow")
    table.add_column("Description", style="white", max_width=50)
    
    for field in result.fields:
        cpu_rating = "🟢" if field.cpu_cost == "low" else "🟡" if field.cpu_cost == "medium" else "🔴"
        table.add_row(
            field.name,
            field.type,
            f"{cpu_rating} {field.cpu_cost}",
            field.description
        )
    
    console.print(table)
    console.print(f"\n[dim]VRL code preview (first 10 lines):[/dim]")
    lines = result.vrl_code.split('\n')[:10]
    for i, line in enumerate(lines, 1):
        console.print(f"[dim]{i:2d}[/dim] {line}")
    if len(result.vrl_code.split('\n')) > 10:
        console.print("[dim]...[/dim]")

@app.command()
def test(
    vrl_file: Path = typer.Argument(..., help="VRL file to test"),
    input_file: Path = typer.Option(None, "--input", "-i", help="Test data file"),
    events: int = typer.Option(100, "--events", "-n", help="Number of test events")
) -> None:
    console.print(f"[blue]Testing VRL parser: {vrl_file}[/blue]")
    

if __name__ == "__main__":
    app()