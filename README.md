# Plotly Cloud Templates

A collection of ready-to-deploy Dash application templates built with 100% open-source software and optimized for [Plotly Cloud](https://cloud.plotly.com).

## 🚀 Available Templates

This repository contains a diverse collection of Dash applications that showcase different use cases and functionalities:

### 🎮 Games & Interactive Apps
- **[Werdle](./werdle/)** - A Wordle-inspired word guessing game
- **[Sudoku](./sudoku/)** - Interactive Sudoku puzzle game with multiple difficulty levels
- **[Guess the Flag](./guess-the-flag/)** - Educational flag identification game
- **[Tamadashi](./tamadashi/)** - Interactive dashboard application

### 📊 Data Visualization & Analytics
- **[Movie Genre Trends](./movie-genre-trends/)** - Analyze and visualize movie genre popularity over time
- **[Montreal Metro Incidents](./montreal-metro-incidents/)** - Transit incident data analysis and visualization
- **[Montreal Events](./montreal-events/)** - Event tracking and analytics dashboard
- **[Coffee Flavours](./coffee-flavours/)** - Coffee data visualization and analysis

### 📰 Content & News
- **[Dash News](./dash-news/)** - Modern, responsive news dashboard template

## 🛠️ Technology Stack

All templates are built using 100% open-source technologies:

- **[Dash](https://dash.plotly.com/)** - Web framework for building analytical web applications
- **[Plotly](https://plotly.com/python/)** - Interactive plotting and visualization library
- **[Pandas](https://pandas.pydata.org/)** - Data manipulation and analysis
- **[Gunicorn](https://gunicorn.org/)** - Python WSGI HTTP Server for deployment
- **Additional libraries** as needed per template (see individual `requirements.txt` files)

## ⚡ Quick Start

### Deploy to Plotly Cloud (Recommended)

1. Visit [cloud.plotly.com](https://cloud.plotly.com)
2. Create a new app and drag and drop all the files for a given template
3. Plotly Cloud will automatically detect the `requirements.txt` and deploy your app!

### Run Locally

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/plotly-cloud-templates.git
   cd plotly-cloud-templates
   ```

2. **Navigate to your chosen template**:
   ```bash
   cd <template-name>  # e.g., cd werdle
   ```

3. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application**:
   ```bash
   python app.py
   ```

6. **Open your browser** and navigate to `http://127.0.0.1:8050`

## 📁 Template Structure

Each template follows a consistent structure:

```
template-name/
├── app.py              # Main Dash application
├── requirements.txt    # Python dependencies
├── assets/            # CSS, images, and other static files
├── data/              # Data files (if applicable)
└── README.md          # Template-specific documentation
```

## 🚀 Deploy to Plotly Cloud

[Plotly Cloud](https://cloud.plotly.com) makes it incredibly easy to deploy these templates:

1. **No server management** - Focus on your app, not infrastructure
2. **Automatic scaling** - Handle traffic spikes seamlessly
3. **Built-in authentication** - Secure your apps with ease
4. **Custom domains** - Use your own domain name
5. **Collaboration tools** - Share and collaborate on apps
6. **Enterprise features** - Advanced security and compliance options

## 🤝 Contributing

We welcome contributions! Feel free to:

- Add new templates
- Improve existing templates  
- Fix bugs or enhance documentation
- Share your deployed apps

## 🔗 Links

- [Plotly Cloud](https://cloud.plotly.com) - Deploy your Dash apps
- [Dash Documentation](https://dash.plotly.com/) - Learn more about Dash
- [Plotly](https://plotly.com/) - Plotly graphing library docs
- [Dash Community Forum](https://community.plotly.com/) - Get help and share ideas

---
