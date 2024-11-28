'use strict';
 
exports.handler = function(event, context, callback) {
  // Get request and request headers
  const request = event.Records[0].cf.request;
  const headers = request.headers;
 
  // Configure authentication credentials
  const authUser = '$AUTH_USER';
  const authPass = '$AUTH_PASS';
 
  // Construct the HTTP Basic Auth string
  const authString = 'Basic ' + new Buffer(authUser + ':' + authPass).toString('base64');


  if (headers.host[0].value == "gs.otakaro.digitaltwins.nz") {
    // This unfortunately needs to be wide open.
    callback(null, request);
  }

  // This is a bit of a hack - A browser will specify the origin for a backend request along with the host. 
  // Given the basic auth is a barrier to entry and not an outright security risk,
  if (typeof headers.origin !== 'undefined') {
    if (headers.host[0].value == "api.otakaro.digitaltwins.nz" && headers.origin[0].value == "https://otakaro.digitaltwins.nz") {
      callback(null, request);
    }
  }

  if (typeof headers.authorization == 'undefined' || headers.authorization[0].value != authString) {
    const body = 'Unauthorized';
    const response = {
      status: '401',
      statusDescription: 'Unauthorized',
      body: body,
      headers: {
        'www-authenticate': [{
          key: 'WWW-Authenticate',
          value: 'Basic'
        }]
      },
    };
    callback(null, response);
  }
 
  // Continue request processing if authentication passed
  callback(null, request);
};


