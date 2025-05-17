# JobMatchAI

An intelligent job matching system that automatically scrapes, analyzes, and ranks LinkedIn job listings based on your professional preferences using AI.

## Overview

JobMatchAI is an educational proof-of-concept that demonstrates how AI can be leveraged to streamline the job search process. The system automatically scrapes LinkedIn job listings on a scheduled basis, analyzes them using LLM-powered relevance scoring, and presents you with personalized job recommendations that match your skills and preferences.

## Key Features

- **Automated Job Scraping**: Schedule daily or weekly job searches from LinkedIn based on your preferred job titles and locations
- **AI-Powered Analysis**: Uses LLM analysis to determine job relevance based on your skills and preferences
- **Personalized Matching**: Custom relevance scoring that considers your required skills, preferred skills, and job title preferences
- **Job Management Workflow**: Track jobs through your application pipeline (viewed, saved, applied, rejected)
- **Scheduling System**: Run job searches and analysis automatically on your preferred schedule

## System Components

- **Database**: SQLite with connection pooling and transaction management
- **Scraper Service**: LinkedIn job scraper with configurable search parameters
- **Analysis Service**: LLM-powered job analysis using OpenAI API
- **User Management**: Account creation, authentication, and preference management
- **Scheduler**: Background job scheduling for automated scraping and analysis
- **Orchestrator**: High-level service coordination

## Getting Started

1. Clone this repository
2. Install dependencies:
3. Set up your configuration (see `config.py`)
4. Initialize the database
5. Run the application

## Usage

1. Create a user account
2. Set up your job preferences:
- Target job titles
- Required and preferred skills
- Locations of interest
- Experience levels
3. Configure your scraping schedule (daily/weekly)
4. The system will automatically:
- Scrape LinkedIn for jobs matching your criteria
- Analyze job relevance using AI
- Present you with relevant matches
5. Review your job matches and update their status as you progress

## Important Disclaimer

**Use this tool responsibly and at your own risk.** LinkedIn's terms of service may prohibit automated scraping. We strongly recommend:

- Using a dedicated LinkedIn account separate from your professional profile
- Setting reasonable rate limits and delays between requests
- Not running the scraper excessively
- Being aware that LinkedIn may detect and block automated scraping

This project is intended as an educational proof-of-concept demonstrating AI application in job search automation. The authors do not endorse or encourage any violation of LinkedIn's terms of service.

## Configuration

The system requires the following configuration:
- OpenAI API Key (for job analysis)
- LinkedIn scraping parameters
- Database configuration

See `config.py` for all available options.

## Project Structure

- `database/`: Database models and connection management
- `constants/`: System-wide constants and configuration
- `services/`: Core services (analysis, scraping, scheduling, etc.)
- `utils/`: Utility functions

## Contributing

This is an educational project. Feel free to fork, modify, and extend it for your own learning purposes.

## License

This project is available for educational purposes only. The LinkedIn scraper component should be used responsibly and in accordance with LinkedIn's terms of service.
