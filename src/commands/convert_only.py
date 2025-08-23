from pathlib import Path
import click

from ..converters.markdown import convert_md_to_html
from ..utils.log import info, success


@click.command(name="convert")
@click.option('--input-md-file', type=click.Path(exists=True), required=True)
@click.option('--html-file', required=True, type=str)
@click.option('--pandoc-args', default='')
@click.pass_context
def convert_only(ctx, input_md_file, html_file, pandoc_args):
    """Convert Markdown to HTML via pandoc, no upload."""
    out = Path(html_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    info(ctx, f"Converting: {input_md_file} → {html_file}")
    convert_md_to_html(input_md_file, out, pandoc_args=pandoc_args)
    success(ctx, f"Wrote {html_file}")
