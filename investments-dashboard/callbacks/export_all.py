from datetime import datetime

from dash import callback, Input, Output, dcc, html

from utils.pdf_export import create_pdf_report
from utils.data_loader import get_time_series_data, get_sector_allocation
from components.charts import (
    create_hypothetical_growth_chart,
    create_performance_line_chart,
    create_sector_donut_chart,
    create_fee_comparison_chart,
)
from pages.performance import create_drawdown_chart


@callback(
    Output("download-pdf-all", "data"),
    Output("pdf-status-all", "children"),
    Input("generate-pdf-all-btn", "n_clicks"),
    prevent_initial_call=True,
)
def generate_all_pdf(n_clicks):
    if not n_clicks:
        return None, ""
    try:
        ts_data = get_time_series_data()
        sector_data = get_sector_allocation()

        figures = [
            create_hypothetical_growth_chart().to_dict(),
            create_performance_line_chart(ts_data, "Performance Over Time").to_dict(),
            create_drawdown_chart(ts_data).to_dict(),
            create_sector_donut_chart(sector_data, "Sector Allocation").to_dict(),
            create_fee_comparison_chart().to_dict(),
        ]
        titles = [
            "Hypothetical Growth",
            "Price Performance",
            "Drawdown Analysis",
            "Sector Allocation",
            "Fee Comparison",
        ]

        pdf_bytes = create_pdf_report(
            figures=figures,
            titles=titles,
            report_title="Investment Report",
        )
        filename = f"investment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return dcc.send_bytes(pdf_bytes, filename), ""
    except Exception as e:
        import traceback
        return None, html.Div(
            f"PDF error: {e}\n{traceback.format_exc()}",
            style={"color": "red", "white-space": "pre-wrap", "fontSize": "12px"},
        )
