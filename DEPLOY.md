# Deployment Guide

This guide covers deploying the Canvas to Open edX Converter to various platforms.

## Heroku Deployment (Recommended)

Heroku provides the easiest deployment path with automatic scaling and free tier options.

### Prerequisites

- Heroku account ([sign up free](https://signup.heroku.com/))
- Git installed
- Heroku CLI installed ([download](https://devcenter.heroku.com/articles/heroku-cli))

### Quick Deploy

```bash
# 1. Login to Heroku
heroku login

# 2. Create a new Heroku app
heroku create your-app-name

# 3. Deploy the application
git push heroku main

# 4. Open your app
heroku open
```

Your converter is now live at `https://your-app-name.herokuapp.com`

### Configuration

#### Environment Variables

Set custom configurations via environment variables:

```bash
# Example configurations
heroku config:set FLASK_ENV=production
heroku config:set MAX_FILE_SIZE=100
```

#### Dyno Type

Free tier works for testing:
```bash
heroku ps:scale web=1
```

For production with better performance:
```bash
heroku ps:type hobby  # $7/month, no sleeping, 512MB RAM
```

#### Log Monitoring

View application logs in real-time:
```bash
heroku logs --tail
```

### Troubleshooting Heroku

**Build Failures**
- Verify `requirements.txt` includes all dependencies
- Check `runtime.txt` specifies correct Python version (3.11.7)
- Review build logs: `heroku logs --tail`

**Application Errors**
- Check if app is running: `heroku ps`
- View error logs: `heroku logs --tail`
- Restart app: `heroku restart`

**Timeout Issues**
- Free dynos timeout after 30 seconds
- Upgrade to Hobby tier for longer request timeouts
- For very large courses, consider background job processing

## Local Development

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py

# Application runs at http://localhost:5000
```

### Testing Locally

```bash
# Run tests
pytest tests/

# Test conversion via CLI
python cli.py test-course.imscc output/ --verbose
```

## Docker Deployment

### Build Image

```bash
docker build -t canvas-converter .
```

### Run Container

```bash
docker run -p 5000:5000 canvas-converter
```

### Docker Compose

```yaml
version: '3'
services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
```

Run with:
```bash
docker-compose up
```

## Production Server (Linux)

### Using Gunicorn

```bash
# Install gunicorn
pip install gunicorn

# Run with 4 workers
gunicorn app:app --workers 4 --bind 0.0.0.0:5000
```

### Using Nginx

1. **Install Nginx**
```bash
sudo apt-get install nginx
```

2. **Configure Nginx** (`/etc/nginx/sites-available/converter`)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

3. **Enable site**
```bash
sudo ln -s /etc/nginx/sites-available/converter /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Systemd Service

Create `/etc/systemd/system/converter.service`:

```ini
[Unit]
Description=Canvas Converter
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/converter
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn app:app --workers 4 --bind 127.0.0.1:5000

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable converter
sudo systemctl start converter
```

## AWS Elastic Beanstalk

### Prerequisites
- AWS account
- EB CLI installed

### Deploy

```bash
# Initialize
eb init -p python-3.11 canvas-converter

# Create environment
eb create canvas-converter-env

# Deploy
eb deploy

# Open app
eb open
```

## Google Cloud Platform

### App Engine Deployment

1. **Create `app.yaml`**
```yaml
runtime: python311
entrypoint: gunicorn -b :$PORT app:app

instance_class: F2

automatic_scaling:
  max_instances: 10
```

2. **Deploy**
```bash
gcloud app deploy
```

## Configuration Options

### File Size Limits

Edit `app.py` to adjust maximum upload size:

```python
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB
```

### Timeout Settings

For Heroku, timeout is 30 seconds on free tier. For longer conversions:
- Upgrade to Hobby or higher
- Implement background job processing with Celery/Redis

### Security

#### For Production Deployments

1. **Add Authentication**

```python
from flask_httpauth import HTTPBasicAuth
auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    # Implement your auth logic
    pass

@app.before_request
@auth.login_required
def before_request():
    pass
```

2. **Enable HTTPS**

On Heroku, HTTPS is automatic. For custom servers:
```bash
# Using Let's Encrypt
sudo certbot --nginx -d your-domain.com
```

3. **Environment Variables**

Never commit secrets to Git. Use environment variables:
```bash
export SECRET_KEY="your-secret-key"
export DATABASE_URL="your-database-url"
```

4. **Rate Limiting**

```python
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=lambda: request.remote_addr,
    default_limits=["100 per hour"]
)
```

## Monitoring

### Application Monitoring

**Heroku**
```bash
# View metrics
heroku logs --tail

# Add-ons for monitoring
heroku addons:create papertrail
```

**Custom Logging**
```python
import logging
logging.basicConfig(level=logging.INFO)
```

### Error Tracking

Consider integrating:
- Sentry for error tracking
- New Relic for performance monitoring
- LogDNA for log management

## Scaling

### Vertical Scaling (Heroku)

```bash
# Upgrade dyno type
heroku ps:type performance-m
```

### Horizontal Scaling (Heroku)

```bash
# Add more dynos
heroku ps:scale web=3
```

### Database Considerations

For high-volume usage, consider adding:
- Redis for caching
- PostgreSQL for job queuing
- Celery for background processing

## Performance Optimization

### Caching

```python
from flask_caching import Cache

cache = Cache(app, config={'CACHE_TYPE': 'simple'})
```

### Compression

```python
from flask_compress import Compress

Compress(app)
```

### CDN for Static Assets

For production, serve static files via CDN (CloudFront, CloudFlare, etc.)

## Backup and Recovery

### Database Backups (if applicable)

```bash
# Heroku Postgres
heroku pg:backups:capture
heroku pg:backups:download
```

### Code Backups

Maintain your repository on GitHub/GitLab with regular commits.

## Maintenance

### Updating Dependencies

```bash
# Update requirements
pip freeze > requirements.txt

# Deploy updates
git add requirements.txt
git commit -m "Update dependencies"
git push heroku main
```

### Health Checks

Implement a health check endpoint:

```python
@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})
```

## Support

For deployment issues:
- Check platform-specific documentation
- Review application logs
- Test locally first
- Verify all environment variables are set

## Additional Resources

- [Heroku Python Documentation](https://devcenter.heroku.com/categories/python-support)
- [Flask Deployment Options](https://flask.palletsprojects.com/en/latest/deploying/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
