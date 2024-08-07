
### Automated API documentation website building.

This small webpack project creates the webpages for our API documentation.
It is linked to GitHub Actions to merge with out Python docs.

The source for this documentation is the API spec defined at `src/static/api_documentation.yml`

#### Usage
    npm ci
    npm run build
    
The built documentation can be viewed by opening `dist/index.html` in browser.
