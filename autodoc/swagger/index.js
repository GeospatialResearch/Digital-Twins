// Load swagger UI into HTML document/DOM using Javascript to read specification yml

import SwaggerUI from 'swagger-ui'
import 'swagger-ui/dist/swagger-ui.css';

// Load API specification into webpage UI
const spec = require('../../src/static/api_documentation.yml');

const ui = SwaggerUI({
  spec,
  dom_id: '#swagger',
  // Disable 'Try it out' for all HTTP methods.
  supportedSubmitMethods: [],
});

ui.initOAuth({
  appName: "Swagger UI Webpack Demo",
  // See https://demo.identityserver.io/ for configuration details.
  clientId: 'implicit'
});
