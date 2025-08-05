# Dash News Dashboard

A modern, responsive Dash application with a beautiful header and main content area.

## Features

- **Modern Design**: Clean, professional interface with gradient header
- **Responsive Layout**: Works on desktop and mobile devices
- **Interactive Charts**: Sample scatter plot with Plotly
- **Custom Styling**: Beautiful CSS styling in `assets/custom.css`
- **Modular Structure**: Easy to extend and customize

## Setup

1. **Activate the conda environment**:
   ```bash
   conda activate dash-news
   ```

2. **Install dependencies** (if not already installed):
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Open your browser** and navigate to:
   ```
   http://127.0.0.1:8050
   ```

## Project Structure

```
dash-news/
├── app.py              # Main Dash application
├── assets/
│   └── custom.css      # Custom CSS styling
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Customization

- **Add new charts**: Modify the `app.py` file to include additional `dcc.Graph` components
- **Update styling**: Edit `assets/custom.css` to change colors, fonts, and layout
- **Add new content**: Extend the layout in `app.py` with additional HTML components

## Dependencies

- `dash`: Web framework for building analytical web applications
- `pandas`: Data manipulation and analysis
- `plotly`: Interactive plotting library

## Development

The app runs in debug mode by default, which enables:
- Hot reloading when you make changes
- Detailed error messages
- Development server features 