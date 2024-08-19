import SwaggerUI from 'swagger-ui'
import 'swagger-ui/dist/swagger-ui.css';

const spec = require('../../src/static/api_documentation.yml');

const ui = SwaggerUI({
  spec,
  dom_id: '#swagger',
});

ui.initOAuth({
  appName: "Swagger UI Webpack Demo",
  // See https://demo.identityserver.io/ for configuration details.
  clientId: 'implicit'
});
