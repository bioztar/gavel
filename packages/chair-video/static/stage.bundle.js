var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __commonJS = (cb, mod) => function __require() {
  try {
    return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
  } catch (e) {
    throw mod = 0, e;
  }
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));

// node_modules/@fal-ai/client/src/middleware.js
var require_middleware = __commonJS({
  "node_modules/@fal-ai/client/src/middleware.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.TARGET_URL_HEADER = void 0;
    exports.withMiddleware = withMiddleware;
    exports.withProxy = withProxy;
    function withMiddleware(...middlewares) {
      const isDefined = (middleware) => typeof middleware === "function";
      return (config) => __awaiter(this, void 0, void 0, function* () {
        let currentConfig = Object.assign({}, config);
        for (const middleware of middlewares.filter(isDefined)) {
          currentConfig = yield middleware(currentConfig);
        }
        return currentConfig;
      });
    }
    exports.TARGET_URL_HEADER = "x-fal-target-url";
    function shouldProxy(when) {
      const env = {
        isBrowser: typeof window !== "undefined" && typeof window.document !== "undefined"
      };
      if (typeof when === "function") {
        return when(env);
      }
      if (when === "always") {
        return true;
      }
      return env.isBrowser;
    }
    function withProxy(config) {
      return (requestConfig) => {
        if (requestConfig.headers && exports.TARGET_URL_HEADER in requestConfig.headers) {
          return Promise.resolve(requestConfig);
        }
        if (!shouldProxy(config.when)) {
          return Promise.resolve(requestConfig);
        }
        return Promise.resolve(Object.assign(Object.assign({}, requestConfig), { url: config.targetUrl, headers: Object.assign(Object.assign({}, requestConfig.headers || {}), { [exports.TARGET_URL_HEADER]: requestConfig.url }) }));
      };
    }
  }
});

// node_modules/@fal-ai/client/src/headers.js
var require_headers = __commonJS({
  "node_modules/@fal-ai/client/src/headers.js"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.RUNNER_HINT_HEADER = exports.QUEUE_PRIORITY_HEADER = exports.REQUEST_TIMEOUT_TYPE_HEADER = exports.REQUEST_TIMEOUT_HEADER = exports.MIN_REQUEST_TIMEOUT_SECONDS = void 0;
    exports.validateTimeoutHeader = validateTimeoutHeader;
    exports.buildTimeoutHeaders = buildTimeoutHeaders;
    exports.MIN_REQUEST_TIMEOUT_SECONDS = 1;
    exports.REQUEST_TIMEOUT_HEADER = "x-fal-request-timeout";
    exports.REQUEST_TIMEOUT_TYPE_HEADER = "x-fal-request-timeout-type";
    exports.QUEUE_PRIORITY_HEADER = "x-fal-queue-priority";
    exports.RUNNER_HINT_HEADER = "x-fal-runner-hint";
    function validateTimeoutHeader(timeout) {
      if (typeof timeout !== "number" || isNaN(timeout)) {
        throw new Error(`Timeout must be a number, got ${timeout}`);
      }
      if (timeout <= exports.MIN_REQUEST_TIMEOUT_SECONDS) {
        throw new Error(`Timeout must be greater than ${exports.MIN_REQUEST_TIMEOUT_SECONDS} seconds`);
      }
      return timeout.toString();
    }
    function buildTimeoutHeaders(timeout) {
      if (timeout === void 0) {
        return {};
      }
      return {
        [exports.REQUEST_TIMEOUT_HEADER]: validateTimeoutHeader(timeout)
      };
    }
  }
});

// node_modules/@fal-ai/client/src/response.js
var require_response = __commonJS({
  "node_modules/@fal-ai/client/src/response.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.ValidationError = exports.ApiError = void 0;
    exports.defaultResponseHandler = defaultResponseHandler;
    exports.resultResponseHandler = resultResponseHandler;
    var headers_1 = require_headers();
    var REQUEST_ID_HEADER = "x-fal-request-id";
    var ApiError = class extends Error {
      constructor({ message, status, body, requestId, timeoutType }) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.body = body;
        this.requestId = requestId || "";
        this.timeoutType = timeoutType;
      }
      /**
       * Returns true if this error was caused by a user-specified timeout
       * (via startTimeout parameter). These errors should NOT be retried.
       */
      get isUserTimeout() {
        return this.status === 504 && this.timeoutType === "user";
      }
    };
    exports.ApiError = ApiError;
    var ValidationError = class extends ApiError {
      constructor(args) {
        super(args);
        this.name = "ValidationError";
      }
      get fieldErrors() {
        if (typeof this.body.detail === "string") {
          return [
            {
              loc: ["body"],
              msg: this.body.detail,
              type: "value_error"
            }
          ];
        }
        return this.body.detail || [];
      }
      getFieldErrors(field) {
        return this.fieldErrors.filter((error) => error.loc[error.loc.length - 1] === field);
      }
    };
    exports.ValidationError = ValidationError;
    function defaultResponseHandler(response) {
      return __awaiter(this, void 0, void 0, function* () {
        var _a;
        const { status, statusText } = response;
        const contentType = (_a = response.headers.get("Content-Type")) !== null && _a !== void 0 ? _a : "";
        const requestId = response.headers.get(REQUEST_ID_HEADER) || void 0;
        const timeoutType = response.headers.get(headers_1.REQUEST_TIMEOUT_TYPE_HEADER) || void 0;
        if (!response.ok) {
          if (contentType.includes("application/json")) {
            const body = yield response.json();
            const ErrorType = status === 422 ? ValidationError : ApiError;
            throw new ErrorType({
              message: body.message || statusText,
              status,
              body,
              requestId,
              timeoutType
            });
          }
          throw new ApiError({
            message: `HTTP ${status}: ${statusText}`,
            status,
            requestId,
            timeoutType
          });
        }
        if (contentType.includes("application/json")) {
          return response.json();
        }
        if (contentType.includes("text/html")) {
          return response.text();
        }
        if (contentType.includes("application/octet-stream")) {
          return response.arrayBuffer();
        }
        return response.text();
      });
    }
    function resultResponseHandler(response) {
      return __awaiter(this, void 0, void 0, function* () {
        const data = yield defaultResponseHandler(response);
        return {
          data,
          requestId: response.headers.get(REQUEST_ID_HEADER) || ""
        };
      });
    }
  }
});

// node_modules/@fal-ai/client/src/utils.js
var require_utils = __commonJS({
  "node_modules/@fal-ai/client/src/utils.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.ensureEndpointIdFormat = ensureEndpointIdFormat;
    exports.parseEndpointId = parseEndpointId;
    exports.resolveEndpointPath = resolveEndpointPath;
    exports.isValidUrl = isValidUrl;
    exports.throttle = throttle;
    exports.isReact = isReact;
    exports.isPlainObject = isPlainObject;
    exports.sleep = sleep;
    function ensureEndpointIdFormat(id) {
      if (/^[a-z][a-z\d+.-]*:\/\//i.test(id)) {
        throw new Error(`Invalid endpoint: ${id}. URLs must be https:// and point at a fal.run or fal.ai host; anything else must be an endpoint id in the format <appOwner>/<appId>.`);
      }
      const parts = id.split("/");
      if (parts.length > 1) {
        return id;
      }
      const [, appOwner, appId] = /^([0-9]+)-([a-zA-Z0-9-]+)$/.exec(id) || [];
      if (appOwner && appId) {
        return `${appOwner}/${appId}`;
      }
      throw new Error(`Invalid app id: ${id}. Must be in the format <appOwner>/<appId>`);
    }
    var ENDPOINT_NAMESPACES = ["workflows", "comfy"];
    function parseEndpointId(id) {
      const normalizedId = ensureEndpointIdFormat(id);
      const parts = normalizedId.split("/");
      if (ENDPOINT_NAMESPACES.includes(parts[0])) {
        return {
          owner: parts[1],
          alias: parts[2],
          path: parts.slice(3).join("/") || void 0,
          namespace: parts[0]
        };
      }
      return {
        owner: parts[0],
        alias: parts[1],
        path: parts.slice(2).join("/") || void 0
      };
    }
    function resolveEndpointPath(app, path, defaultPath) {
      if (path) {
        return `/${path.replace(/^\/+/, "")}`;
      }
      if (app.endsWith(defaultPath)) {
        return void 0;
      }
      return defaultPath;
    }
    function isValidUrl(url) {
      try {
        const parsed = new URL(url);
        const hostname = parsed.hostname.toLowerCase();
        return parsed.protocol === "https:" && // No explicit nonstandard port: the URL parser normalizes :443 away, so any remaining port
        // targets a different listener — credentials must not follow a fal hostname to it.
        parsed.port === "" && (hostname === "fal.ai" || hostname.endsWith(".fal.ai") || hostname === "fal.run" || hostname.endsWith(".fal.run"));
      } catch (_) {
        return false;
      }
    }
    function throttle(func, limit, leading = false) {
      let lastFunc;
      let lastRan;
      return (...args) => {
        if (!lastRan && leading) {
          func(...args);
          lastRan = Date.now();
        } else {
          if (lastFunc) {
            clearTimeout(lastFunc);
          }
          lastFunc = setTimeout(() => {
            if (Date.now() - lastRan >= limit) {
              func(...args);
              lastRan = Date.now();
            }
          }, limit - (Date.now() - lastRan));
        }
      };
    }
    var isRunningInReact;
    function isReact() {
      if (isRunningInReact === void 0) {
        const stack = new Error().stack;
        isRunningInReact = !!stack && (stack.includes("node_modules/react-dom/") || stack.includes("node_modules/next/"));
      }
      return isRunningInReact;
    }
    function isPlainObject(value) {
      return !!value && Object.getPrototypeOf(value) === Object.prototype;
    }
    function sleep(ms) {
      return __awaiter(this, void 0, void 0, function* () {
        return new Promise((resolve) => setTimeout(resolve, ms));
      });
    }
  }
});

// node_modules/@fal-ai/client/src/retry.js
var require_retry = __commonJS({
  "node_modules/@fal-ai/client/src/retry.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.DEFAULT_RETRY_OPTIONS = exports.DEFAULT_RETRYABLE_STATUS_CODES = void 0;
    exports.isRetryableNetworkError = isRetryableNetworkError;
    exports.isRetryableError = isRetryableError;
    exports.calculateBackoffDelay = calculateBackoffDelay;
    exports.executeWithRetry = executeWithRetry;
    var response_1 = require_response();
    var utils_1 = require_utils();
    exports.DEFAULT_RETRYABLE_STATUS_CODES = [429, 502, 503, 504];
    exports.DEFAULT_RETRY_OPTIONS = {
      maxRetries: 3,
      baseDelay: 1e3,
      maxDelay: 3e4,
      backoffMultiplier: 2,
      retryableStatusCodes: exports.DEFAULT_RETRYABLE_STATUS_CODES,
      enableJitter: true
    };
    var RETRYABLE_NETWORK_ERROR_CODES = /* @__PURE__ */ new Set([
      "ECONNABORTED",
      "ECONNREFUSED",
      "ECONNRESET",
      "EAI_AGAIN",
      "EHOSTUNREACH",
      "ENETUNREACH",
      "ENOTFOUND",
      "EPIPE",
      "ETIMEDOUT",
      "UND_ERR_BODY_TIMEOUT",
      "UND_ERR_CONNECT_TIMEOUT",
      "UND_ERR_HEADERS_TIMEOUT",
      "UND_ERR_SOCKET"
    ]);
    function isRetryableNetworkError(error) {
      if (!error || typeof error !== "object") {
        return false;
      }
      const seen = /* @__PURE__ */ new Set();
      let current = error;
      let sawTransportShape = false;
      while (current && typeof current === "object" && !seen.has(current)) {
        seen.add(current);
        const name = current.name;
        if (name === "AbortError" || name === "TimeoutError") {
          return false;
        }
        const code = current.code;
        if (typeof code === "string" && RETRYABLE_NETWORK_ERROR_CODES.has(code)) {
          sawTransportShape = true;
        }
        current = current.cause;
      }
      if (sawTransportShape) {
        return true;
      }
      if (error instanceof TypeError && typeof error.message === "string" && /fetch failed/i.test(error.message)) {
        return true;
      }
      return false;
    }
    function isRetryableError(error, retryableStatusCodes) {
      if (error instanceof response_1.ApiError) {
        if (error.isUserTimeout) {
          return false;
        }
        return retryableStatusCodes.includes(error.status);
      }
      return isRetryableNetworkError(error);
    }
    function calculateBackoffDelay(attempt, baseDelay, maxDelay, backoffMultiplier, enableJitter) {
      const exponentialDelay = Math.min(baseDelay * Math.pow(backoffMultiplier, attempt), maxDelay);
      if (enableJitter) {
        const jitter = 0.25 * exponentialDelay * (Math.random() * 2 - 1);
        return Math.max(0, exponentialDelay + jitter);
      }
      return exponentialDelay;
    }
    function executeWithRetry(operation, options, onRetry) {
      return __awaiter(this, void 0, void 0, function* () {
        const metrics = {
          totalAttempts: 0,
          totalDelay: 0
        };
        let lastError;
        for (let attempt = 0; attempt <= options.maxRetries; attempt++) {
          metrics.totalAttempts++;
          try {
            const result = yield operation();
            return { result, metrics };
          } catch (error) {
            lastError = error;
            metrics.lastError = error;
            if (attempt === options.maxRetries || !isRetryableError(error, options.retryableStatusCodes)) {
              throw error;
            }
            const delay = calculateBackoffDelay(attempt, options.baseDelay, options.maxDelay, options.backoffMultiplier, options.enableJitter);
            metrics.totalDelay += delay;
            if (onRetry) {
              onRetry(attempt + 1, error, delay);
            }
            yield (0, utils_1.sleep)(delay);
          }
        }
        throw lastError;
      });
    }
  }
});

// node_modules/@fal-ai/client/package.json
var require_package = __commonJS({
  "node_modules/@fal-ai/client/package.json"(exports, module) {
    module.exports = {
      name: "@fal-ai/client",
      description: "The fal.ai client for JavaScript and TypeScript",
      version: "1.11.0-alpha.3",
      license: "MIT",
      repository: {
        type: "git",
        url: "https://github.com/fal-ai/fal-js.git",
        directory: "libs/client"
      },
      keywords: [
        "fal",
        "client",
        "ai",
        "ml",
        "typescript"
      ],
      exports: {
        ".": "./src/index.js",
        "./endpoints": "./src/types/endpoints.js",
        "./realtime": "./src/realtime/index.js",
        "./realtime/extension": "./src/realtime/extension.js",
        "./realtime/ice": "./src/realtime/ice.js",
        "./realtime/lucy": "./src/realtime/lucy.js",
        "./realtime/testing": "./src/realtime/testing.js",
        "./realtime/websocket": "./src/realtime/websocket.js",
        "./realtime/wma": "./src/realtime/wma.js"
      },
      typesVersions: {
        "*": {
          endpoints: [
            "src/types/endpoints.d.ts"
          ],
          realtime: [
            "src/realtime/index.d.ts"
          ],
          "realtime/extension": [
            "src/realtime/extension.d.ts"
          ],
          "realtime/ice": [
            "src/realtime/ice.d.ts"
          ],
          "realtime/lucy": [
            "src/realtime/lucy.d.ts"
          ],
          "realtime/testing": [
            "src/realtime/testing.d.ts"
          ],
          "realtime/websocket": [
            "src/realtime/websocket.d.ts"
          ],
          "realtime/wma": [
            "src/realtime/wma.d.ts"
          ]
        }
      },
      sideEffects: false,
      main: "./src/index.js",
      types: "./src/index.d.ts",
      dependencies: {
        "@msgpack/msgpack": "^3.0.0-beta2",
        "eventsource-parser": "^1.1.2",
        robot3: "^0.4.1"
      },
      engines: {
        node: ">=18.0.0"
      },
      type: "commonjs"
    };
  }
});

// node_modules/@fal-ai/client/src/runtime.js
var require_runtime = __commonJS({
  "node_modules/@fal-ai/client/src/runtime.js"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.isBrowser = isBrowser;
    exports.getUserAgent = getUserAgent;
    function isBrowser() {
      return typeof window !== "undefined" && typeof window.document !== "undefined";
    }
    var memoizedUserAgent = null;
    function getUserAgent() {
      if (memoizedUserAgent !== null) {
        return memoizedUserAgent;
      }
      const packageInfo = require_package();
      memoizedUserAgent = `${packageInfo.name}/${packageInfo.version}`;
      return memoizedUserAgent;
    }
  }
});

// node_modules/@fal-ai/client/src/config.js
var require_config = __commonJS({
  "node_modules/@fal-ai/client/src/config.js"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.credentialsFromEnv = void 0;
    exports.resolveDefaultFetch = resolveDefaultFetch;
    exports.createConfig = createConfig;
    exports.getRestApiUrl = getRestApiUrl;
    var middleware_1 = require_middleware();
    var response_1 = require_response();
    var retry_1 = require_retry();
    var runtime_1 = require_runtime();
    function resolveDefaultFetch() {
      if (typeof fetch === "undefined") {
        throw new Error("Your environment does not support fetch. Please provide your own fetch implementation.");
      }
      return fetch;
    }
    function hasEnvVariables() {
      return typeof process !== "undefined" && process.env && (typeof process.env.FAL_KEY !== "undefined" || typeof process.env.FAL_KEY_ID !== "undefined" && typeof process.env.FAL_KEY_SECRET !== "undefined");
    }
    var credentialsFromEnv = () => {
      if (!hasEnvVariables()) {
        return void 0;
      }
      if (typeof process.env.FAL_KEY !== "undefined") {
        return process.env.FAL_KEY;
      }
      return process.env.FAL_KEY_ID ? `${process.env.FAL_KEY_ID}:${process.env.FAL_KEY_SECRET}` : void 0;
    };
    exports.credentialsFromEnv = credentialsFromEnv;
    var DEFAULT_CONFIG = {
      credentials: exports.credentialsFromEnv,
      suppressLocalCredentialsWarning: false,
      requestMiddleware: (request) => Promise.resolve(request),
      responseHandler: response_1.defaultResponseHandler,
      retry: retry_1.DEFAULT_RETRY_OPTIONS
    };
    function createConfig(config) {
      var _a;
      let configuration = Object.assign(Object.assign(Object.assign({}, DEFAULT_CONFIG), config), {
        fetch: (_a = config.fetch) !== null && _a !== void 0 ? _a : resolveDefaultFetch(),
        // Merge retry configuration with defaults
        retry: Object.assign(Object.assign({}, retry_1.DEFAULT_RETRY_OPTIONS), config.retry || {})
      });
      if (config.proxyUrl) {
        const proxy = typeof config.proxyUrl === "string" ? { url: config.proxyUrl } : config.proxyUrl;
        configuration = Object.assign(Object.assign({}, configuration), { requestMiddleware: (0, middleware_1.withMiddleware)(configuration.requestMiddleware, (0, middleware_1.withProxy)({ targetUrl: proxy.url, when: proxy.when })) });
      }
      const { credentials: resolveCredentials, suppressLocalCredentialsWarning } = configuration;
      const credentials = typeof resolveCredentials === "function" ? resolveCredentials() : resolveCredentials;
      if ((0, runtime_1.isBrowser)() && credentials && !suppressLocalCredentialsWarning) {
        console.warn("The fal credentials are exposed in the browser's environment. That's not recommended for production use cases.");
      }
      return configuration;
    }
    function getRestApiUrl() {
      return "https://rest.fal.ai";
    }
  }
});

// node_modules/@fal-ai/client/src/request.js
var require_request = __commonJS({
  "node_modules/@fal-ai/client/src/request.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    var __rest = exports && exports.__rest || function(s, e) {
      var t = {};
      for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0)
        t[p] = s[p];
      if (s != null && typeof Object.getOwnPropertySymbols === "function")
        for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
          if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i]))
            t[p[i]] = s[p[i]];
        }
      return t;
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.dispatchRequest = dispatchRequest;
    exports.buildUrl = buildUrl;
    var retry_1 = require_retry();
    var runtime_1 = require_runtime();
    var utils_1 = require_utils();
    var isCloudflareWorkers = typeof navigator !== "undefined" && (navigator === null || navigator === void 0 ? void 0 : navigator.userAgent) === "Cloudflare-Workers";
    function dispatchRequest(params) {
      return __awaiter(this, void 0, void 0, function* () {
        var _a;
        const { targetUrl, input, config, options = {} } = params;
        const { credentials: credentialsValue, requestMiddleware, responseHandler, fetch: fetch2 } = config;
        const retryOptions = Object.assign(Object.assign({}, config.retry), options.retry || {});
        const executeRequest = () => __awaiter(this, void 0, void 0, function* () {
          var _a2, _b, _c;
          const userAgent = (0, runtime_1.isBrowser)() ? {} : { "User-Agent": (0, runtime_1.getUserAgent)() };
          const credentials = typeof credentialsValue === "function" ? credentialsValue() : credentialsValue;
          const { method, url, headers } = yield requestMiddleware({
            method: ((_b = (_a2 = params.method) !== null && _a2 !== void 0 ? _a2 : options.method) !== null && _b !== void 0 ? _b : "post").toUpperCase(),
            url: targetUrl,
            headers: params.headers
          });
          const authHeader = credentials ? { Authorization: `Key ${credentials}` } : {};
          const requestHeaders = Object.assign(Object.assign(Object.assign(Object.assign({}, authHeader), { Accept: "application/json", "Content-Type": "application/json" }), userAgent), headers !== null && headers !== void 0 ? headers : {});
          const { responseHandler: customResponseHandler, retry: _ } = options, requestInit = __rest(options, ["responseHandler", "retry"]);
          const response = yield fetch2(url, Object.assign(Object.assign(Object.assign(Object.assign({}, requestInit), { method, headers: Object.assign(Object.assign({}, requestHeaders), (_c = requestInit.headers) !== null && _c !== void 0 ? _c : {}) }), !isCloudflareWorkers && { mode: "cors" }), { signal: options.signal, body: method.toLowerCase() !== "get" && input ? JSON.stringify(input) : void 0 }));
          const handleResponse = customResponseHandler !== null && customResponseHandler !== void 0 ? customResponseHandler : responseHandler;
          return yield handleResponse(response);
        });
        let lastError;
        for (let attempt = 0; attempt <= retryOptions.maxRetries; attempt++) {
          try {
            return yield executeRequest();
          } catch (error) {
            lastError = error;
            const shouldNotRetry = attempt === retryOptions.maxRetries || !(0, retry_1.isRetryableError)(error, retryOptions.retryableStatusCodes) || ((_a = options.signal) === null || _a === void 0 ? void 0 : _a.aborted);
            if (shouldNotRetry) {
              throw error;
            }
            const delay = (0, retry_1.calculateBackoffDelay)(attempt, retryOptions.baseDelay, retryOptions.maxDelay, retryOptions.backoffMultiplier, retryOptions.enableJitter);
            yield (0, utils_1.sleep)(delay);
          }
        }
        throw lastError;
      });
    }
    function buildUrl(id, options = {}) {
      var _a, _b;
      const method = ((_a = options.method) !== null && _a !== void 0 ? _a : "post").toLowerCase();
      const path = ((_b = options.path) !== null && _b !== void 0 ? _b : "").replace(/^\//, "").replace(/\/{2,}/, "/");
      const input = options.input;
      const params = Object.assign(Object.assign({}, options.query || {}), method === "get" ? input : {});
      const queryParams = Object.keys(params).length > 0 ? `?${new URLSearchParams(params).toString()}` : "";
      if ((0, utils_1.isValidUrl)(id)) {
        const url2 = id.endsWith("/") ? id : `${id}/`;
        return `${url2}${path}${queryParams}`;
      }
      const appId = (0, utils_1.ensureEndpointIdFormat)(id);
      const subdomain = options.subdomain ? `${options.subdomain}.` : "";
      const url = `https://${subdomain}fal.run/${appId}/${path}`;
      return `${url.replace(/\/$/, "")}${queryParams}`;
    }
  }
});

// node_modules/@fal-ai/client/src/storage.js
var require_storage = __commonJS({
  "node_modules/@fal-ai/client/src/storage.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.OBJECT_LIFECYCYLE_PREFERENCE_HEADER = void 0;
    exports.getExpirationDurationSeconds = getExpirationDurationSeconds;
    exports.buildObjectLifecycleHeaders = buildObjectLifecycleHeaders;
    exports.createStorageClient = createStorageClient;
    var config_1 = require_config();
    var request_1 = require_request();
    var utils_1 = require_utils();
    exports.OBJECT_LIFECYCYLE_PREFERENCE_HEADER = "x-fal-object-lifecycle-preference";
    var EXPIRATION_VALUES = {
      never: void 0,
      immediate: 60,
      "1h": 3600,
      "1d": 86400,
      "7d": 604800,
      "30d": 2592e3,
      "1y": 31536e3
    };
    function getExpirationDurationSeconds(lifecycle) {
      const { expiresIn } = lifecycle;
      if (expiresIn === void 0) {
        return void 0;
      }
      return typeof expiresIn === "number" ? expiresIn : EXPIRATION_VALUES[expiresIn];
    }
    function buildUploadLifecycleConfig(lifecycle) {
      if (!lifecycle) {
        return void 0;
      }
      const expirationDurationSeconds = getExpirationDurationSeconds(lifecycle);
      const lifecycleConfig = {};
      if (expirationDurationSeconds !== void 0) {
        lifecycleConfig.expiration_duration_seconds = expirationDurationSeconds;
      }
      if (lifecycle.initialAcl !== void 0) {
        lifecycleConfig.initial_acl = lifecycle.initialAcl;
      }
      return Object.keys(lifecycleConfig).length > 0 ? lifecycleConfig : void 0;
    }
    function buildObjectLifecycleHeaders(lifecycle) {
      const lifecycleConfig = buildUploadLifecycleConfig(lifecycle);
      if (!lifecycleConfig) {
        return {};
      }
      return {
        [exports.OBJECT_LIFECYCYLE_PREFERENCE_HEADER]: JSON.stringify(lifecycleConfig)
      };
    }
    function getExtensionFromContentType(contentType) {
      var _a;
      const [, fileType] = contentType.split("/");
      return (_a = fileType.split(/[-;]/)[0]) !== null && _a !== void 0 ? _a : "bin";
    }
    function initiateUpload(file, config, contentType, lifecycle) {
      return __awaiter(this, void 0, void 0, function* () {
        const filename = file.name || `${Date.now()}.${getExtensionFromContentType(contentType)}`;
        const headers = {};
        const lifecycleConfig = buildUploadLifecycleConfig(lifecycle);
        if (lifecycleConfig) {
          headers["X-Fal-Object-Lifecycle"] = JSON.stringify(lifecycleConfig);
        }
        return yield (0, request_1.dispatchRequest)({
          method: "POST",
          // NOTE: We want to test V3 without making it the default at the API level
          targetUrl: `${(0, config_1.getRestApiUrl)()}/storage/upload/initiate?storage_type=fal-cdn-v3`,
          input: {
            content_type: contentType,
            file_name: filename
          },
          config,
          headers
        });
      });
    }
    function initiateMultipartUpload(file, config, contentType, lifecycle) {
      return __awaiter(this, void 0, void 0, function* () {
        const filename = file.name || `${Date.now()}.${getExtensionFromContentType(contentType)}`;
        const headers = {};
        const lifecycleConfig = buildUploadLifecycleConfig(lifecycle);
        if (lifecycleConfig) {
          headers["X-Fal-Object-Lifecycle"] = JSON.stringify(lifecycleConfig);
        }
        return yield (0, request_1.dispatchRequest)({
          method: "POST",
          targetUrl: `${(0, config_1.getRestApiUrl)()}/storage/upload/initiate-multipart?storage_type=fal-cdn-v3`,
          input: {
            content_type: contentType,
            file_name: filename
          },
          config,
          headers
        });
      });
    }
    function partUploadRetries(uploadUrl_1, chunk_1, config_2) {
      return __awaiter(this, arguments, void 0, function* (uploadUrl, chunk, config, tries = 3) {
        if (tries === 0) {
          throw new Error("Part upload failed, retries exhausted");
        }
        const { fetch: fetch2, responseHandler } = config;
        try {
          const response = yield fetch2(uploadUrl, {
            method: "PUT",
            body: chunk
          });
          return yield responseHandler(response);
        } catch (error) {
          return yield partUploadRetries(uploadUrl, chunk, config, tries - 1);
        }
      });
    }
    function multipartUpload(file, config, lifecycle) {
      return __awaiter(this, void 0, void 0, function* () {
        const { fetch: fetch2, responseHandler } = config;
        const contentType = file.type || "application/octet-stream";
        const { upload_url: uploadUrl, file_url: url } = yield initiateMultipartUpload(file, config, contentType, lifecycle);
        const chunkSize = 10 * 1024 * 1024;
        const chunks = Math.ceil(file.size / chunkSize);
        const parsedUrl = new URL(uploadUrl);
        const responses = [];
        for (let i = 0; i < chunks; i++) {
          const start = i * chunkSize;
          const end = Math.min(start + chunkSize, file.size);
          const chunk = file.slice(start, end);
          const partNumber = i + 1;
          const partUploadUrl = `${parsedUrl.origin}${parsedUrl.pathname}/${partNumber}${parsedUrl.search}`;
          responses.push(yield partUploadRetries(partUploadUrl, chunk, config));
        }
        const completeUrl = `${parsedUrl.origin}${parsedUrl.pathname}/complete${parsedUrl.search}`;
        const response = yield fetch2(completeUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            parts: responses.map((mpart) => ({
              partNumber: mpart.partNumber,
              etag: mpart.etag
            }))
          })
        });
        yield responseHandler(response);
        return url;
      });
    }
    function createStorageClient({ config }) {
      const ref = {
        upload: (file, options) => __awaiter(this, void 0, void 0, function* () {
          const lifecycle = options === null || options === void 0 ? void 0 : options.lifecycle;
          if (file.size > 90 * 1024 * 1024) {
            return yield multipartUpload(file, config, lifecycle);
          }
          const contentType = file.type || "application/octet-stream";
          const { fetch: fetch2, responseHandler } = config;
          const { upload_url: uploadUrl, file_url: url } = yield initiateUpload(file, config, contentType, lifecycle);
          const response = yield fetch2(uploadUrl, {
            method: "PUT",
            body: file,
            headers: {
              "Content-Type": file.type || "application/octet-stream"
            }
          });
          yield responseHandler(response);
          return url;
        }),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        transformInput: (input) => __awaiter(this, void 0, void 0, function* () {
          if (Array.isArray(input)) {
            return Promise.all(input.map((item) => ref.transformInput(item)));
          } else if (input instanceof Blob) {
            return yield ref.upload(input);
          } else if ((0, utils_1.isPlainObject)(input)) {
            const inputObject = input;
            const promises = Object.entries(inputObject).map((_a) => __awaiter(this, [_a], void 0, function* ([key, value]) {
              return [key, yield ref.transformInput(value)];
            }));
            const results = yield Promise.all(promises);
            return Object.fromEntries(results);
          }
          return input;
        })
      };
      return ref;
    }
  }
});

// node_modules/eventsource-parser/dist/index.cjs
var require_dist = __commonJS({
  "node_modules/eventsource-parser/dist/index.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", {
      value: true
    });
    function createParser(onParse) {
      let isFirstChunk;
      let buffer;
      let startingPosition;
      let startingFieldLength;
      let eventId;
      let eventName;
      let data;
      reset();
      return {
        feed,
        reset
      };
      function reset() {
        isFirstChunk = true;
        buffer = "";
        startingPosition = 0;
        startingFieldLength = -1;
        eventId = void 0;
        eventName = void 0;
        data = "";
      }
      function feed(chunk) {
        buffer = buffer ? buffer + chunk : chunk;
        if (isFirstChunk && hasBom(buffer)) {
          buffer = buffer.slice(BOM.length);
        }
        isFirstChunk = false;
        const length = buffer.length;
        let position = 0;
        let discardTrailingNewline = false;
        while (position < length) {
          if (discardTrailingNewline) {
            if (buffer[position] === "\n") {
              ++position;
            }
            discardTrailingNewline = false;
          }
          let lineLength = -1;
          let fieldLength = startingFieldLength;
          let character;
          for (let index = startingPosition; lineLength < 0 && index < length; ++index) {
            character = buffer[index];
            if (character === ":" && fieldLength < 0) {
              fieldLength = index - position;
            } else if (character === "\r") {
              discardTrailingNewline = true;
              lineLength = index - position;
            } else if (character === "\n") {
              lineLength = index - position;
            }
          }
          if (lineLength < 0) {
            startingPosition = length - position;
            startingFieldLength = fieldLength;
            break;
          } else {
            startingPosition = 0;
            startingFieldLength = -1;
          }
          parseEventStreamLine(buffer, position, fieldLength, lineLength);
          position += lineLength + 1;
        }
        if (position === length) {
          buffer = "";
        } else if (position > 0) {
          buffer = buffer.slice(position);
        }
      }
      function parseEventStreamLine(lineBuffer, index, fieldLength, lineLength) {
        if (lineLength === 0) {
          if (data.length > 0) {
            onParse({
              type: "event",
              id: eventId,
              event: eventName || void 0,
              data: data.slice(0, -1)
              // remove trailing newline
            });
            data = "";
            eventId = void 0;
          }
          eventName = void 0;
          return;
        }
        const noValue = fieldLength < 0;
        const field = lineBuffer.slice(index, index + (noValue ? lineLength : fieldLength));
        let step = 0;
        if (noValue) {
          step = lineLength;
        } else if (lineBuffer[index + fieldLength + 1] === " ") {
          step = fieldLength + 2;
        } else {
          step = fieldLength + 1;
        }
        const position = index + step;
        const valueLength = lineLength - step;
        const value = lineBuffer.slice(position, position + valueLength).toString();
        if (field === "data") {
          data += value ? "".concat(value, "\n") : "\n";
        } else if (field === "event") {
          eventName = value;
        } else if (field === "id" && !value.includes("\0")) {
          eventId = value;
        } else if (field === "retry") {
          const retry = parseInt(value, 10);
          if (!Number.isNaN(retry)) {
            onParse({
              type: "reconnect-interval",
              value: retry
            });
          }
        }
      }
    }
    var BOM = [239, 187, 191];
    function hasBom(buffer) {
      return BOM.every((charCode, index) => buffer.charCodeAt(index) === charCode);
    }
    exports.createParser = createParser;
  }
});

// node_modules/@fal-ai/client/src/auth.js
var require_auth = __commonJS({
  "node_modules/@fal-ai/client/src/auth.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.TOKEN_EXPIRATION_SECONDS = void 0;
    exports.getTemporaryAuthToken = getTemporaryAuthToken;
    var config_1 = require_config();
    var request_1 = require_request();
    var utils_1 = require_utils();
    exports.TOKEN_EXPIRATION_SECONDS = 120;
    function getTemporaryAuthToken(app, config) {
      return __awaiter(this, void 0, void 0, function* () {
        const appId = (0, utils_1.parseEndpointId)(app);
        const token = yield (0, request_1.dispatchRequest)({
          method: "POST",
          targetUrl: `${(0, config_1.getRestApiUrl)()}/tokens/`,
          config,
          input: {
            allowed_apps: [appId.alias],
            token_expiration: exports.TOKEN_EXPIRATION_SECONDS
          }
        });
        if (typeof token !== "string" && token["detail"]) {
          return token["detail"];
        }
        return token;
      });
    }
  }
});

// node_modules/@fal-ai/client/src/streaming.js
var require_streaming = __commonJS({
  "node_modules/@fal-ai/client/src/streaming.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    var __await = exports && exports.__await || function(v) {
      return this instanceof __await ? (this.v = v, this) : new __await(v);
    };
    var __asyncGenerator = exports && exports.__asyncGenerator || function(thisArg, _arguments, generator) {
      if (!Symbol.asyncIterator) throw new TypeError("Symbol.asyncIterator is not defined.");
      var g = generator.apply(thisArg, _arguments || []), i, q = [];
      return i = {}, verb("next"), verb("throw"), verb("return", awaitReturn), i[Symbol.asyncIterator] = function() {
        return this;
      }, i;
      function awaitReturn(f) {
        return function(v) {
          return Promise.resolve(v).then(f, reject);
        };
      }
      function verb(n, f) {
        if (g[n]) {
          i[n] = function(v) {
            return new Promise(function(a, b) {
              q.push([n, v, a, b]) > 1 || resume(n, v);
            });
          };
          if (f) i[n] = f(i[n]);
        }
      }
      function resume(n, v) {
        try {
          step(g[n](v));
        } catch (e) {
          settle(q[0][3], e);
        }
      }
      function step(r) {
        r.value instanceof __await ? Promise.resolve(r.value.v).then(fulfill, reject) : settle(q[0][2], r);
      }
      function fulfill(value) {
        resume("next", value);
      }
      function reject(value) {
        resume("throw", value);
      }
      function settle(f, v) {
        if (f(v), q.shift(), q.length) resume(q[0][0], q[0][1]);
      }
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.FalStream = void 0;
    exports.createStreamingClient = createStreamingClient;
    var eventsource_parser_1 = require_dist();
    var auth_1 = require_auth();
    var request_1 = require_request();
    var response_1 = require_response();
    var utils_1 = require_utils();
    var CONTENT_TYPE_EVENT_STREAM = "text/event-stream";
    var EVENT_STREAM_TIMEOUT = 15 * 1e3;
    var FalStream = class {
      constructor(endpointId, config, options) {
        var _a;
        this.listeners = /* @__PURE__ */ new Map();
        this.buffer = [];
        this.currentData = void 0;
        this.lastEventTimestamp = 0;
        this.streamClosed = false;
        this._requestId = null;
        this.abortController = new AbortController();
        this.start = () => __awaiter(this, void 0, void 0, function* () {
          var _a2, _b, _c;
          const { endpointId: endpointId2, options: options2 } = this;
          const { input, method = "post", connectionMode = "server", tokenProvider } = options2;
          try {
            if (connectionMode === "client") {
              const appId = (0, utils_1.isValidUrl)(endpointId2) ? endpointId2 : (0, utils_1.ensureEndpointIdFormat)(endpointId2);
              const resolvedPath = (_a2 = (0, utils_1.resolveEndpointPath)(endpointId2, void 0, "/stream")) !== null && _a2 !== void 0 ? _a2 : "";
              const fetchToken = tokenProvider ? () => tokenProvider(`${appId}${resolvedPath}`) : () => {
                console.warn('[fal.stream] Using the default token provider is deprecated. Please provide a `tokenProvider` function when using `connectionMode: "client"`. See https://docs.fal.ai/fal-client/authentication for more information.');
                return (0, auth_1.getTemporaryAuthToken)(endpointId2, this.config);
              };
              const token = yield fetchToken();
              const { fetch: fetch2 } = this.config;
              const parsedUrl = new URL(this.url);
              parsedUrl.searchParams.set("fal_jwt_token", token);
              const response = yield fetch2(parsedUrl.toString(), {
                method: method.toUpperCase(),
                headers: {
                  accept: (_b = options2.accept) !== null && _b !== void 0 ? _b : CONTENT_TYPE_EVENT_STREAM,
                  "content-type": "application/json"
                },
                body: input && method !== "get" ? JSON.stringify(input) : void 0,
                signal: this.abortController.signal
              });
              this._requestId = response.headers.get("x-fal-request-id");
              return yield this.handleResponse(response);
            }
            return yield (0, request_1.dispatchRequest)({
              method: method.toUpperCase(),
              targetUrl: this.url,
              input,
              config: this.config,
              options: {
                headers: {
                  accept: (_c = options2.accept) !== null && _c !== void 0 ? _c : CONTENT_TYPE_EVENT_STREAM
                },
                responseHandler: (response) => __awaiter(this, void 0, void 0, function* () {
                  this._requestId = response.headers.get("x-fal-request-id");
                  return yield this.handleResponse(response);
                }),
                signal: this.abortController.signal
              }
            });
          } catch (error) {
            this.handleError(error);
          }
        });
        this.handleResponse = (response) => __awaiter(this, void 0, void 0, function* () {
          var _a2, _b;
          if (!response.ok) {
            try {
              yield (0, response_1.defaultResponseHandler)(response);
            } catch (error) {
              this.emit("error", error);
            }
            return;
          }
          const body = response.body;
          if (!body) {
            this.emit("error", new response_1.ApiError({
              message: "Response body is empty.",
              status: 400,
              body: void 0,
              requestId: this._requestId || void 0
            }));
            return;
          }
          const isEventStream = ((_a2 = response.headers.get("content-type")) !== null && _a2 !== void 0 ? _a2 : "").startsWith(CONTENT_TYPE_EVENT_STREAM);
          if (!isEventStream) {
            const reader2 = body.getReader();
            const emitRawChunk = () => {
              reader2.read().then(({ done, value }) => {
                if (done) {
                  this.emit("done", this.currentData);
                  return;
                }
                this.buffer.push(value);
                this.currentData = value;
                this.emit("data", value);
                emitRawChunk();
              });
            };
            emitRawChunk();
            return;
          }
          const decoder = new TextDecoder("utf-8");
          const reader = response.body.getReader();
          const parser = (0, eventsource_parser_1.createParser)((event) => {
            if (event.type === "event") {
              const data = event.data;
              try {
                const parsedData = JSON.parse(data);
                this.buffer.push(parsedData);
                this.currentData = parsedData;
                this.emit("data", parsedData);
                this.emit("message", parsedData);
              } catch (e) {
                this.emit("error", e);
              }
            }
          });
          const timeout = (_b = this.options.timeout) !== null && _b !== void 0 ? _b : EVENT_STREAM_TIMEOUT;
          const readPartialResponse = () => __awaiter(this, void 0, void 0, function* () {
            const { value, done } = yield reader.read();
            this.lastEventTimestamp = Date.now();
            parser.feed(decoder.decode(value));
            if (Date.now() - this.lastEventTimestamp > timeout) {
              this.emit("error", new response_1.ApiError({
                message: `Event stream timed out after ${(timeout / 1e3).toFixed(0)} seconds with no messages.`,
                status: 408,
                requestId: this._requestId || void 0
              }));
            }
            if (!done) {
              readPartialResponse().catch(this.handleError);
            } else {
              this.emit("done", this.currentData);
            }
          });
          readPartialResponse().catch(this.handleError);
          return;
        });
        this.handleError = (error) => {
          var _a2;
          if (error.name === "AbortError" || this.signal.aborted) {
            return;
          }
          const apiError = error instanceof response_1.ApiError ? error : new response_1.ApiError({
            message: (_a2 = error.message) !== null && _a2 !== void 0 ? _a2 : "An unknown error occurred",
            status: 500,
            requestId: this._requestId || void 0
          });
          this.emit("error", apiError);
          return;
        };
        this.on = (type, listener) => {
          var _a2;
          if (!this.listeners.has(type)) {
            this.listeners.set(type, []);
          }
          (_a2 = this.listeners.get(type)) === null || _a2 === void 0 ? void 0 : _a2.push(listener);
        };
        this.emit = (type, event) => {
          const listeners = this.listeners.get(type) || [];
          for (const listener of listeners) {
            listener(event);
          }
        };
        this.done = () => __awaiter(this, void 0, void 0, function* () {
          return this.donePromise;
        });
        this.abort = (reason) => {
          if (!this.streamClosed) {
            this.abortController.abort(reason);
          }
        };
        this.endpointId = endpointId;
        this.config = config;
        this.url = (_a = options.url) !== null && _a !== void 0 ? _a : (0, request_1.buildUrl)(endpointId, {
          path: (0, utils_1.resolveEndpointPath)(endpointId, void 0, "/stream"),
          query: options.queryParams
        });
        this.options = options;
        this.donePromise = new Promise((resolve, reject) => {
          if (this.streamClosed) {
            reject(new response_1.ApiError({
              message: "Streaming connection is already closed.",
              status: 400,
              body: void 0,
              requestId: this._requestId || void 0
            }));
          }
          this.signal.addEventListener("abort", () => {
            var _a2;
            resolve((_a2 = this.currentData) !== null && _a2 !== void 0 ? _a2 : {});
          });
          this.on("done", (data) => {
            this.streamClosed = true;
            resolve(data);
          });
          this.on("error", (error) => {
            this.streamClosed = true;
            reject(error);
          });
        });
        if (options.signal) {
          options.signal.addEventListener("abort", () => {
            this.abortController.abort();
          });
        }
        this.start().catch(this.handleError);
      }
      [Symbol.asyncIterator]() {
        return __asyncGenerator(this, arguments, function* _a() {
          let running = true;
          const stopAsyncIterator = () => running = false;
          this.on("error", stopAsyncIterator);
          this.on("done", stopAsyncIterator);
          while (running || this.buffer.length > 0) {
            const data = this.buffer.shift();
            if (data) {
              yield yield __await(data);
            }
            yield __await(new Promise((resolve) => setTimeout(resolve, 16)));
          }
        });
      }
      /**
       * Gets the `AbortSignal` instance that can be used to listen for abort events.
       *
       * **Note:** this signal is internal to the `FalStream` instance. If you pass your
       * own abort signal, the `FalStream` will listen to it and abort it appropriately.
       *
       * @returns the `AbortSignal` instance.
       * @see https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal
       */
      get signal() {
        return this.abortController.signal;
      }
      /**
       * Gets the request id of the streaming request.
       *
       * @returns the request id.
       */
      get requestId() {
        return this._requestId;
      }
    };
    exports.FalStream = FalStream;
    function createStreamingClient({ config, storage }) {
      return {
        stream(endpointId, options) {
          return __awaiter(this, void 0, void 0, function* () {
            const input = options.input ? yield storage.transformInput(options.input) : void 0;
            return new FalStream(endpointId, config, Object.assign(Object.assign({}, options), { input }));
          });
        }
      };
    }
  }
});

// node_modules/@fal-ai/client/src/queue.js
var require_queue = __commonJS({
  "node_modules/@fal-ai/client/src/queue.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    var __rest = exports && exports.__rest || function(s, e) {
      var t = {};
      for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0)
        t[p] = s[p];
      if (s != null && typeof Object.getOwnPropertySymbols === "function")
        for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
          if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i]))
            t[p[i]] = s[p[i]];
        }
      return t;
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.createQueueClient = void 0;
    var headers_1 = require_headers();
    var request_1 = require_request();
    var response_1 = require_response();
    var retry_1 = require_retry();
    var storage_1 = require_storage();
    var streaming_1 = require_streaming();
    var utils_1 = require_utils();
    var DEFAULT_POLL_INTERVAL = 500;
    var QUEUE_RETRY_CONFIG = {
      maxRetries: 3,
      baseDelay: 1e3,
      maxDelay: 6e4,
      retryableStatusCodes: retry_1.DEFAULT_RETRYABLE_STATUS_CODES
    };
    var QUEUE_STATUS_RETRY_CONFIG = {
      maxRetries: 5,
      baseDelay: 1e3,
      maxDelay: 3e4,
      retryableStatusCodes: [...retry_1.DEFAULT_RETRYABLE_STATUS_CODES, 500]
    };
    var createQueueClient = ({ config, storage }) => {
      const ref = {
        submit(endpointId, options) {
          return __awaiter(this, void 0, void 0, function* () {
            const { webhookUrl, priority, hint, startTimeout, headers, storageSettings } = options, runOptions = __rest(options, ["webhookUrl", "priority", "hint", "startTimeout", "headers", "storageSettings"]);
            const input = options.input ? yield storage.transformInput(options.input) : void 0;
            const extraHeaders = Object.fromEntries(Object.entries(headers !== null && headers !== void 0 ? headers : {}).map(([key, value]) => [
              key.toLowerCase(),
              value
            ]));
            return (0, request_1.dispatchRequest)({
              method: options.method,
              targetUrl: (0, request_1.buildUrl)(endpointId, Object.assign(Object.assign({}, runOptions), { subdomain: "queue", query: webhookUrl ? { fal_webhook: webhookUrl } : void 0 })),
              headers: Object.assign(Object.assign(Object.assign(Object.assign(Object.assign({}, extraHeaders), (0, storage_1.buildObjectLifecycleHeaders)(storageSettings)), { [headers_1.QUEUE_PRIORITY_HEADER]: priority !== null && priority !== void 0 ? priority : "normal" }), hint && { [headers_1.RUNNER_HINT_HEADER]: hint }), (0, headers_1.buildTimeoutHeaders)(startTimeout)),
              input,
              config,
              options: {
                signal: options.abortSignal,
                retry: QUEUE_RETRY_CONFIG
              }
            });
          });
        },
        status(endpointId_1, _a) {
          return __awaiter(this, arguments, void 0, function* (endpointId, { requestId, logs = false, abortSignal }) {
            const appId = (0, utils_1.parseEndpointId)(endpointId);
            const prefix = appId.namespace ? `${appId.namespace}/` : "";
            return (0, request_1.dispatchRequest)({
              method: "get",
              targetUrl: (0, request_1.buildUrl)(`${prefix}${appId.owner}/${appId.alias}`, {
                subdomain: "queue",
                query: { logs: logs ? "1" : "0" },
                path: `/requests/${requestId}/status`
              }),
              config,
              options: {
                signal: abortSignal,
                retry: QUEUE_STATUS_RETRY_CONFIG
              }
            });
          });
        },
        streamStatus(endpointId_1, _a) {
          return __awaiter(this, arguments, void 0, function* (endpointId, { requestId, logs = false, connectionMode }) {
            const appId = (0, utils_1.parseEndpointId)(endpointId);
            const prefix = appId.namespace ? `${appId.namespace}/` : "";
            const queryParams = {
              logs: logs ? "1" : "0"
            };
            const url = (0, request_1.buildUrl)(`${prefix}${appId.owner}/${appId.alias}`, {
              subdomain: "queue",
              path: `/requests/${requestId}/status/stream`,
              query: queryParams
            });
            return new streaming_1.FalStream(endpointId, config, {
              url,
              method: "get",
              connectionMode,
              queryParams
            });
          });
        },
        subscribeToStatus(endpointId, options) {
          return __awaiter(this, void 0, void 0, function* () {
            const requestId = options.requestId;
            const timeout = options.timeout;
            let timeoutId = void 0;
            const handleCancelError = () => {
            };
            if (options.mode === "streaming") {
              const status = yield ref.streamStatus(endpointId, {
                requestId,
                logs: options.logs,
                connectionMode: "connectionMode" in options ? options.connectionMode : void 0
              });
              const logs = [];
              if (timeout) {
                timeoutId = setTimeout(() => {
                  status.abort();
                  ref.cancel(endpointId, { requestId }).catch(handleCancelError);
                  throw new Error(`Client timed out waiting for the request to complete after ${timeout}ms`);
                }, timeout);
              }
              status.on("data", (data) => {
                if (options.onQueueUpdate) {
                  if ("logs" in data && Array.isArray(data.logs) && data.logs.length > 0) {
                    logs.push(...data.logs);
                  }
                  options.onQueueUpdate("logs" in data ? Object.assign(Object.assign({}, data), { logs }) : data);
                }
              });
              const doneStatus = yield status.done();
              if (timeoutId) {
                clearTimeout(timeoutId);
              }
              return doneStatus;
            }
            return new Promise((resolve, reject) => {
              var _a;
              let pollingTimeoutId;
              const pollInterval = "pollInterval" in options && typeof options.pollInterval === "number" ? (_a = options.pollInterval) !== null && _a !== void 0 ? _a : DEFAULT_POLL_INTERVAL : DEFAULT_POLL_INTERVAL;
              const clearScheduledTasks = () => {
                if (timeoutId) {
                  clearTimeout(timeoutId);
                }
                if (pollingTimeoutId) {
                  clearTimeout(pollingTimeoutId);
                }
              };
              if (timeout) {
                timeoutId = setTimeout(() => {
                  clearScheduledTasks();
                  ref.cancel(endpointId, { requestId }).catch(handleCancelError);
                  reject(new Error(`Client timed out waiting for the request to complete after ${timeout}ms`));
                }, timeout);
              }
              const poll = () => __awaiter(this, void 0, void 0, function* () {
                var _a2;
                try {
                  const requestStatus = yield ref.status(endpointId, {
                    requestId,
                    logs: (_a2 = options.logs) !== null && _a2 !== void 0 ? _a2 : false,
                    abortSignal: options.abortSignal
                  });
                  if (options.onQueueUpdate) {
                    options.onQueueUpdate(requestStatus);
                  }
                  if (requestStatus.status === "COMPLETED") {
                    clearScheduledTasks();
                    resolve(requestStatus);
                    return;
                  }
                  pollingTimeoutId = setTimeout(poll, pollInterval);
                } catch (error) {
                  clearScheduledTasks();
                  reject(error);
                }
              });
              poll().catch(reject);
            });
          });
        },
        result(endpointId_1, _a) {
          return __awaiter(this, arguments, void 0, function* (endpointId, { requestId, abortSignal }) {
            const appId = (0, utils_1.parseEndpointId)(endpointId);
            const prefix = appId.namespace ? `${appId.namespace}/` : "";
            return (0, request_1.dispatchRequest)({
              method: "get",
              targetUrl: (0, request_1.buildUrl)(`${prefix}${appId.owner}/${appId.alias}`, {
                subdomain: "queue",
                path: `/requests/${requestId}`
              }),
              config: Object.assign(Object.assign({}, config), { responseHandler: response_1.resultResponseHandler }),
              options: {
                signal: abortSignal,
                retry: QUEUE_RETRY_CONFIG
              }
            });
          });
        },
        cancel(endpointId_1, _a) {
          return __awaiter(this, arguments, void 0, function* (endpointId, { requestId, abortSignal }) {
            const appId = (0, utils_1.parseEndpointId)(endpointId);
            const prefix = appId.namespace ? `${appId.namespace}/` : "";
            yield (0, request_1.dispatchRequest)({
              method: "put",
              targetUrl: (0, request_1.buildUrl)(`${prefix}${appId.owner}/${appId.alias}`, {
                subdomain: "queue",
                path: `/requests/${requestId}/cancel`
              }),
              config,
              options: {
                signal: abortSignal
              }
            });
          });
        }
      };
      return ref;
    };
    exports.createQueueClient = createQueueClient;
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/utils/utf8.cjs
var require_utf8 = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/utils/utf8.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.utf8Count = utf8Count;
    exports.utf8EncodeJs = utf8EncodeJs;
    exports.utf8EncodeTE = utf8EncodeTE;
    exports.utf8Encode = utf8Encode;
    exports.utf8DecodeJs = utf8DecodeJs;
    exports.utf8DecodeTD = utf8DecodeTD;
    exports.utf8Decode = utf8Decode;
    function utf8Count(str) {
      const strLength = str.length;
      let byteLength = 0;
      let pos = 0;
      while (pos < strLength) {
        let value = str.charCodeAt(pos++);
        if ((value & 4294967168) === 0) {
          byteLength++;
          continue;
        } else if ((value & 4294965248) === 0) {
          byteLength += 2;
        } else {
          if (value >= 55296 && value <= 56319) {
            if (pos < strLength) {
              const extra = str.charCodeAt(pos);
              if ((extra & 64512) === 56320) {
                ++pos;
                value = ((value & 1023) << 10) + (extra & 1023) + 65536;
              }
            }
          }
          if ((value & 4294901760) === 0) {
            byteLength += 3;
          } else {
            byteLength += 4;
          }
        }
      }
      return byteLength;
    }
    function utf8EncodeJs(str, output, outputOffset) {
      const strLength = str.length;
      let offset = outputOffset;
      let pos = 0;
      while (pos < strLength) {
        let value = str.charCodeAt(pos++);
        if ((value & 4294967168) === 0) {
          output[offset++] = value;
          continue;
        } else if ((value & 4294965248) === 0) {
          output[offset++] = value >> 6 & 31 | 192;
        } else {
          if (value >= 55296 && value <= 56319) {
            if (pos < strLength) {
              const extra = str.charCodeAt(pos);
              if ((extra & 64512) === 56320) {
                ++pos;
                value = ((value & 1023) << 10) + (extra & 1023) + 65536;
              }
            }
          }
          if ((value & 4294901760) === 0) {
            output[offset++] = value >> 12 & 15 | 224;
            output[offset++] = value >> 6 & 63 | 128;
          } else {
            output[offset++] = value >> 18 & 7 | 240;
            output[offset++] = value >> 12 & 63 | 128;
            output[offset++] = value >> 6 & 63 | 128;
          }
        }
        output[offset++] = value & 63 | 128;
      }
    }
    var sharedTextEncoder = new TextEncoder();
    var TEXT_ENCODER_THRESHOLD = 50;
    function utf8EncodeTE(str, output, outputOffset) {
      sharedTextEncoder.encodeInto(str, output.subarray(outputOffset));
    }
    function utf8Encode(str, output, outputOffset) {
      if (str.length > TEXT_ENCODER_THRESHOLD) {
        utf8EncodeTE(str, output, outputOffset);
      } else {
        utf8EncodeJs(str, output, outputOffset);
      }
    }
    var CHUNK_SIZE = 4096;
    function utf8DecodeJs(bytes, inputOffset, byteLength) {
      let offset = inputOffset;
      const end = offset + byteLength;
      const units = [];
      let result = "";
      while (offset < end) {
        const byte1 = bytes[offset++];
        if ((byte1 & 128) === 0) {
          units.push(byte1);
        } else if ((byte1 & 224) === 192) {
          const byte2 = bytes[offset++] & 63;
          units.push((byte1 & 31) << 6 | byte2);
        } else if ((byte1 & 240) === 224) {
          const byte2 = bytes[offset++] & 63;
          const byte3 = bytes[offset++] & 63;
          units.push((byte1 & 31) << 12 | byte2 << 6 | byte3);
        } else if ((byte1 & 248) === 240) {
          const byte2 = bytes[offset++] & 63;
          const byte3 = bytes[offset++] & 63;
          const byte4 = bytes[offset++] & 63;
          let unit = (byte1 & 7) << 18 | byte2 << 12 | byte3 << 6 | byte4;
          if (unit > 65535) {
            unit -= 65536;
            units.push(unit >>> 10 & 1023 | 55296);
            unit = 56320 | unit & 1023;
          }
          units.push(unit);
        } else {
          units.push(byte1);
        }
        if (units.length >= CHUNK_SIZE) {
          result += String.fromCharCode(...units);
          units.length = 0;
        }
      }
      if (units.length > 0) {
        result += String.fromCharCode(...units);
      }
      return result;
    }
    var sharedTextDecoder = new TextDecoder();
    var TEXT_DECODER_THRESHOLD = 200;
    function utf8DecodeTD(bytes, inputOffset, byteLength) {
      const stringBytes = bytes.subarray(inputOffset, inputOffset + byteLength);
      return sharedTextDecoder.decode(stringBytes);
    }
    function utf8Decode(bytes, inputOffset, byteLength) {
      if (byteLength > TEXT_DECODER_THRESHOLD) {
        return utf8DecodeTD(bytes, inputOffset, byteLength);
      } else {
        return utf8DecodeJs(bytes, inputOffset, byteLength);
      }
    }
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/ExtData.cjs
var require_ExtData = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/ExtData.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.ExtData = void 0;
    var ExtData = class {
      type;
      data;
      constructor(type, data) {
        this.type = type;
        this.data = data;
      }
    };
    exports.ExtData = ExtData;
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/DecodeError.cjs
var require_DecodeError = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/DecodeError.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.DecodeError = void 0;
    var DecodeError = class _DecodeError extends Error {
      constructor(message) {
        super(message);
        const proto = Object.create(_DecodeError.prototype);
        Object.setPrototypeOf(this, proto);
        Object.defineProperty(this, "name", {
          configurable: true,
          enumerable: false,
          value: _DecodeError.name
        });
      }
    };
    exports.DecodeError = DecodeError;
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/utils/int.cjs
var require_int = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/utils/int.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.UINT32_MAX = void 0;
    exports.setUint64 = setUint64;
    exports.setInt64 = setInt64;
    exports.getInt64 = getInt64;
    exports.getUint64 = getUint64;
    exports.UINT32_MAX = 4294967295;
    function setUint64(view, offset, value) {
      const high = value / 4294967296;
      const low = value;
      view.setUint32(offset, high);
      view.setUint32(offset + 4, low);
    }
    function setInt64(view, offset, value) {
      const high = Math.floor(value / 4294967296);
      const low = value;
      view.setUint32(offset, high);
      view.setUint32(offset + 4, low);
    }
    function getInt64(view, offset) {
      const high = view.getInt32(offset);
      const low = view.getUint32(offset + 4);
      return high * 4294967296 + low;
    }
    function getUint64(view, offset) {
      const high = view.getUint32(offset);
      const low = view.getUint32(offset + 4);
      return high * 4294967296 + low;
    }
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/timestamp.cjs
var require_timestamp = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/timestamp.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.timestampExtension = exports.EXT_TIMESTAMP = void 0;
    exports.encodeTimeSpecToTimestamp = encodeTimeSpecToTimestamp;
    exports.encodeDateToTimeSpec = encodeDateToTimeSpec;
    exports.encodeTimestampExtension = encodeTimestampExtension;
    exports.decodeTimestampToTimeSpec = decodeTimestampToTimeSpec;
    exports.decodeTimestampExtension = decodeTimestampExtension;
    var DecodeError_ts_1 = require_DecodeError();
    var int_ts_1 = require_int();
    exports.EXT_TIMESTAMP = -1;
    var TIMESTAMP32_MAX_SEC = 4294967296 - 1;
    var TIMESTAMP64_MAX_SEC = 17179869184 - 1;
    function encodeTimeSpecToTimestamp({ sec, nsec }) {
      if (sec >= 0 && nsec >= 0 && sec <= TIMESTAMP64_MAX_SEC) {
        if (nsec === 0 && sec <= TIMESTAMP32_MAX_SEC) {
          const rv = new Uint8Array(4);
          const view = new DataView(rv.buffer);
          view.setUint32(0, sec);
          return rv;
        } else {
          const secHigh = sec / 4294967296;
          const secLow = sec & 4294967295;
          const rv = new Uint8Array(8);
          const view = new DataView(rv.buffer);
          view.setUint32(0, nsec << 2 | secHigh & 3);
          view.setUint32(4, secLow);
          return rv;
        }
      } else {
        const rv = new Uint8Array(12);
        const view = new DataView(rv.buffer);
        view.setUint32(0, nsec);
        (0, int_ts_1.setInt64)(view, 4, sec);
        return rv;
      }
    }
    function encodeDateToTimeSpec(date) {
      const msec = date.getTime();
      const sec = Math.floor(msec / 1e3);
      const nsec = (msec - sec * 1e3) * 1e6;
      const nsecInSec = Math.floor(nsec / 1e9);
      return {
        sec: sec + nsecInSec,
        nsec: nsec - nsecInSec * 1e9
      };
    }
    function encodeTimestampExtension(object) {
      if (object instanceof Date) {
        const timeSpec = encodeDateToTimeSpec(object);
        return encodeTimeSpecToTimestamp(timeSpec);
      } else {
        return null;
      }
    }
    function decodeTimestampToTimeSpec(data) {
      const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
      switch (data.byteLength) {
        case 4: {
          const sec = view.getUint32(0);
          const nsec = 0;
          return { sec, nsec };
        }
        case 8: {
          const nsec30AndSecHigh2 = view.getUint32(0);
          const secLow32 = view.getUint32(4);
          const sec = (nsec30AndSecHigh2 & 3) * 4294967296 + secLow32;
          const nsec = nsec30AndSecHigh2 >>> 2;
          return { sec, nsec };
        }
        case 12: {
          const sec = (0, int_ts_1.getInt64)(view, 4);
          const nsec = view.getUint32(0);
          return { sec, nsec };
        }
        default:
          throw new DecodeError_ts_1.DecodeError(`Unrecognized data size for timestamp (expected 4, 8, or 12): ${data.length}`);
      }
    }
    function decodeTimestampExtension(data) {
      const timeSpec = decodeTimestampToTimeSpec(data);
      return new Date(timeSpec.sec * 1e3 + timeSpec.nsec / 1e6);
    }
    exports.timestampExtension = {
      type: exports.EXT_TIMESTAMP,
      encode: encodeTimestampExtension,
      decode: decodeTimestampExtension
    };
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/ExtensionCodec.cjs
var require_ExtensionCodec = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/ExtensionCodec.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.ExtensionCodec = void 0;
    var ExtData_ts_1 = require_ExtData();
    var timestamp_ts_1 = require_timestamp();
    var ExtensionCodec = class _ExtensionCodec {
      static defaultCodec = new _ExtensionCodec();
      // ensures ExtensionCodecType<X> matches ExtensionCodec<X>
      // this will make type errors a lot more clear
      // eslint-disable-next-line @typescript-eslint/naming-convention
      __brand;
      // built-in extensions
      builtInEncoders = [];
      builtInDecoders = [];
      // custom extensions
      encoders = [];
      decoders = [];
      constructor() {
        this.register(timestamp_ts_1.timestampExtension);
      }
      register({ type, encode, decode }) {
        if (type >= 0) {
          this.encoders[type] = encode;
          this.decoders[type] = decode;
        } else {
          const index = -1 - type;
          this.builtInEncoders[index] = encode;
          this.builtInDecoders[index] = decode;
        }
      }
      tryToEncode(object, context) {
        for (let i = 0; i < this.builtInEncoders.length; i++) {
          const encodeExt = this.builtInEncoders[i];
          if (encodeExt != null) {
            const data = encodeExt(object, context);
            if (data != null) {
              const type = -1 - i;
              return new ExtData_ts_1.ExtData(type, data);
            }
          }
        }
        for (let i = 0; i < this.encoders.length; i++) {
          const encodeExt = this.encoders[i];
          if (encodeExt != null) {
            const data = encodeExt(object, context);
            if (data != null) {
              const type = i;
              return new ExtData_ts_1.ExtData(type, data);
            }
          }
        }
        if (object instanceof ExtData_ts_1.ExtData) {
          return object;
        }
        return null;
      }
      decode(data, type, context) {
        const decodeExt = type < 0 ? this.builtInDecoders[-1 - type] : this.decoders[type];
        if (decodeExt) {
          return decodeExt(data, type, context);
        } else {
          return new ExtData_ts_1.ExtData(type, data);
        }
      }
    };
    exports.ExtensionCodec = ExtensionCodec;
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/utils/typedArrays.cjs
var require_typedArrays = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/utils/typedArrays.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.ensureUint8Array = ensureUint8Array;
    function isArrayBufferLike(buffer) {
      return buffer instanceof ArrayBuffer || typeof SharedArrayBuffer !== "undefined" && buffer instanceof SharedArrayBuffer;
    }
    function ensureUint8Array(buffer) {
      if (buffer instanceof Uint8Array) {
        return buffer;
      } else if (ArrayBuffer.isView(buffer)) {
        return new Uint8Array(buffer.buffer, buffer.byteOffset, buffer.byteLength);
      } else if (isArrayBufferLike(buffer)) {
        return new Uint8Array(buffer);
      } else {
        return Uint8Array.from(buffer);
      }
    }
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/Encoder.cjs
var require_Encoder = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/Encoder.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.Encoder = exports.DEFAULT_INITIAL_BUFFER_SIZE = exports.DEFAULT_MAX_DEPTH = void 0;
    var utf8_ts_1 = require_utf8();
    var ExtensionCodec_ts_1 = require_ExtensionCodec();
    var int_ts_1 = require_int();
    var typedArrays_ts_1 = require_typedArrays();
    exports.DEFAULT_MAX_DEPTH = 100;
    exports.DEFAULT_INITIAL_BUFFER_SIZE = 2048;
    var Encoder = class _Encoder {
      extensionCodec;
      context;
      useBigInt64;
      maxDepth;
      initialBufferSize;
      sortKeys;
      forceFloat32;
      ignoreUndefined;
      forceIntegerToFloat;
      pos;
      view;
      bytes;
      entered = false;
      constructor(options) {
        this.extensionCodec = options?.extensionCodec ?? ExtensionCodec_ts_1.ExtensionCodec.defaultCodec;
        this.context = options?.context;
        this.useBigInt64 = options?.useBigInt64 ?? false;
        this.maxDepth = options?.maxDepth ?? exports.DEFAULT_MAX_DEPTH;
        this.initialBufferSize = options?.initialBufferSize ?? exports.DEFAULT_INITIAL_BUFFER_SIZE;
        this.sortKeys = options?.sortKeys ?? false;
        this.forceFloat32 = options?.forceFloat32 ?? false;
        this.ignoreUndefined = options?.ignoreUndefined ?? false;
        this.forceIntegerToFloat = options?.forceIntegerToFloat ?? false;
        this.pos = 0;
        this.view = new DataView(new ArrayBuffer(this.initialBufferSize));
        this.bytes = new Uint8Array(this.view.buffer);
      }
      clone() {
        return new _Encoder({
          extensionCodec: this.extensionCodec,
          context: this.context,
          useBigInt64: this.useBigInt64,
          maxDepth: this.maxDepth,
          initialBufferSize: this.initialBufferSize,
          sortKeys: this.sortKeys,
          forceFloat32: this.forceFloat32,
          ignoreUndefined: this.ignoreUndefined,
          forceIntegerToFloat: this.forceIntegerToFloat
        });
      }
      reinitializeState() {
        this.pos = 0;
      }
      /**
       * This is almost equivalent to {@link Encoder#encode}, but it returns an reference of the encoder's internal buffer and thus much faster than {@link Encoder#encode}.
       *
       * @returns Encodes the object and returns a shared reference the encoder's internal buffer.
       */
      encodeSharedRef(object) {
        if (this.entered) {
          const instance = this.clone();
          return instance.encodeSharedRef(object);
        }
        try {
          this.entered = true;
          this.reinitializeState();
          this.doEncode(object, 1);
          return this.bytes.subarray(0, this.pos);
        } finally {
          this.entered = false;
        }
      }
      /**
       * @returns Encodes the object and returns a copy of the encoder's internal buffer.
       */
      encode(object) {
        if (this.entered) {
          const instance = this.clone();
          return instance.encode(object);
        }
        try {
          this.entered = true;
          this.reinitializeState();
          this.doEncode(object, 1);
          return this.bytes.slice(0, this.pos);
        } finally {
          this.entered = false;
        }
      }
      doEncode(object, depth) {
        if (depth > this.maxDepth) {
          throw new Error(`Too deep objects in depth ${depth}`);
        }
        if (object == null) {
          this.encodeNil();
        } else if (typeof object === "boolean") {
          this.encodeBoolean(object);
        } else if (typeof object === "number") {
          if (!this.forceIntegerToFloat) {
            this.encodeNumber(object);
          } else {
            this.encodeNumberAsFloat(object);
          }
        } else if (typeof object === "string") {
          this.encodeString(object);
        } else if (this.useBigInt64 && typeof object === "bigint") {
          this.encodeBigInt64(object);
        } else {
          this.encodeObject(object, depth);
        }
      }
      ensureBufferSizeToWrite(sizeToWrite) {
        const requiredSize = this.pos + sizeToWrite;
        if (this.view.byteLength < requiredSize) {
          this.resizeBuffer(requiredSize * 2);
        }
      }
      resizeBuffer(newSize) {
        const newBuffer = new ArrayBuffer(newSize);
        const newBytes = new Uint8Array(newBuffer);
        const newView = new DataView(newBuffer);
        newBytes.set(this.bytes);
        this.view = newView;
        this.bytes = newBytes;
      }
      encodeNil() {
        this.writeU8(192);
      }
      encodeBoolean(object) {
        if (object === false) {
          this.writeU8(194);
        } else {
          this.writeU8(195);
        }
      }
      encodeNumber(object) {
        if (!this.forceIntegerToFloat && Number.isSafeInteger(object)) {
          if (object >= 0) {
            if (object < 128) {
              this.writeU8(object);
            } else if (object < 256) {
              this.writeU8(204);
              this.writeU8(object);
            } else if (object < 65536) {
              this.writeU8(205);
              this.writeU16(object);
            } else if (object < 4294967296) {
              this.writeU8(206);
              this.writeU32(object);
            } else if (!this.useBigInt64) {
              this.writeU8(207);
              this.writeU64(object);
            } else {
              this.encodeNumberAsFloat(object);
            }
          } else {
            if (object >= -32) {
              this.writeU8(224 | object + 32);
            } else if (object >= -128) {
              this.writeU8(208);
              this.writeI8(object);
            } else if (object >= -32768) {
              this.writeU8(209);
              this.writeI16(object);
            } else if (object >= -2147483648) {
              this.writeU8(210);
              this.writeI32(object);
            } else if (!this.useBigInt64) {
              this.writeU8(211);
              this.writeI64(object);
            } else {
              this.encodeNumberAsFloat(object);
            }
          }
        } else {
          this.encodeNumberAsFloat(object);
        }
      }
      encodeNumberAsFloat(object) {
        if (this.forceFloat32) {
          this.writeU8(202);
          this.writeF32(object);
        } else {
          this.writeU8(203);
          this.writeF64(object);
        }
      }
      encodeBigInt64(object) {
        if (object >= BigInt(0)) {
          this.writeU8(207);
          this.writeBigUint64(object);
        } else {
          this.writeU8(211);
          this.writeBigInt64(object);
        }
      }
      writeStringHeader(byteLength) {
        if (byteLength < 32) {
          this.writeU8(160 + byteLength);
        } else if (byteLength < 256) {
          this.writeU8(217);
          this.writeU8(byteLength);
        } else if (byteLength < 65536) {
          this.writeU8(218);
          this.writeU16(byteLength);
        } else if (byteLength < 4294967296) {
          this.writeU8(219);
          this.writeU32(byteLength);
        } else {
          throw new Error(`Too long string: ${byteLength} bytes in UTF-8`);
        }
      }
      encodeString(object) {
        const maxHeaderSize = 1 + 4;
        const byteLength = (0, utf8_ts_1.utf8Count)(object);
        this.ensureBufferSizeToWrite(maxHeaderSize + byteLength);
        this.writeStringHeader(byteLength);
        (0, utf8_ts_1.utf8Encode)(object, this.bytes, this.pos);
        this.pos += byteLength;
      }
      encodeObject(object, depth) {
        const ext = this.extensionCodec.tryToEncode(object, this.context);
        if (ext != null) {
          this.encodeExtension(ext);
        } else if (Array.isArray(object)) {
          this.encodeArray(object, depth);
        } else if (ArrayBuffer.isView(object)) {
          this.encodeBinary(object);
        } else if (typeof object === "object") {
          this.encodeMap(object, depth);
        } else {
          throw new Error(`Unrecognized object: ${Object.prototype.toString.apply(object)}`);
        }
      }
      encodeBinary(object) {
        const size = object.byteLength;
        if (size < 256) {
          this.writeU8(196);
          this.writeU8(size);
        } else if (size < 65536) {
          this.writeU8(197);
          this.writeU16(size);
        } else if (size < 4294967296) {
          this.writeU8(198);
          this.writeU32(size);
        } else {
          throw new Error(`Too large binary: ${size}`);
        }
        const bytes = (0, typedArrays_ts_1.ensureUint8Array)(object);
        this.writeU8a(bytes);
      }
      encodeArray(object, depth) {
        const size = object.length;
        if (size < 16) {
          this.writeU8(144 + size);
        } else if (size < 65536) {
          this.writeU8(220);
          this.writeU16(size);
        } else if (size < 4294967296) {
          this.writeU8(221);
          this.writeU32(size);
        } else {
          throw new Error(`Too large array: ${size}`);
        }
        for (const item of object) {
          this.doEncode(item, depth + 1);
        }
      }
      countWithoutUndefined(object, keys) {
        let count = 0;
        for (const key of keys) {
          if (object[key] !== void 0) {
            count++;
          }
        }
        return count;
      }
      encodeMap(object, depth) {
        const keys = Object.keys(object);
        if (this.sortKeys) {
          keys.sort();
        }
        const size = this.ignoreUndefined ? this.countWithoutUndefined(object, keys) : keys.length;
        if (size < 16) {
          this.writeU8(128 + size);
        } else if (size < 65536) {
          this.writeU8(222);
          this.writeU16(size);
        } else if (size < 4294967296) {
          this.writeU8(223);
          this.writeU32(size);
        } else {
          throw new Error(`Too large map object: ${size}`);
        }
        for (const key of keys) {
          const value = object[key];
          if (!(this.ignoreUndefined && value === void 0)) {
            this.encodeString(key);
            this.doEncode(value, depth + 1);
          }
        }
      }
      encodeExtension(ext) {
        if (typeof ext.data === "function") {
          const data = ext.data(this.pos + 6);
          const size2 = data.length;
          if (size2 >= 4294967296) {
            throw new Error(`Too large extension object: ${size2}`);
          }
          this.writeU8(201);
          this.writeU32(size2);
          this.writeI8(ext.type);
          this.writeU8a(data);
          return;
        }
        const size = ext.data.length;
        if (size === 1) {
          this.writeU8(212);
        } else if (size === 2) {
          this.writeU8(213);
        } else if (size === 4) {
          this.writeU8(214);
        } else if (size === 8) {
          this.writeU8(215);
        } else if (size === 16) {
          this.writeU8(216);
        } else if (size < 256) {
          this.writeU8(199);
          this.writeU8(size);
        } else if (size < 65536) {
          this.writeU8(200);
          this.writeU16(size);
        } else if (size < 4294967296) {
          this.writeU8(201);
          this.writeU32(size);
        } else {
          throw new Error(`Too large extension object: ${size}`);
        }
        this.writeI8(ext.type);
        this.writeU8a(ext.data);
      }
      writeU8(value) {
        this.ensureBufferSizeToWrite(1);
        this.view.setUint8(this.pos, value);
        this.pos++;
      }
      writeU8a(values) {
        const size = values.length;
        this.ensureBufferSizeToWrite(size);
        this.bytes.set(values, this.pos);
        this.pos += size;
      }
      writeI8(value) {
        this.ensureBufferSizeToWrite(1);
        this.view.setInt8(this.pos, value);
        this.pos++;
      }
      writeU16(value) {
        this.ensureBufferSizeToWrite(2);
        this.view.setUint16(this.pos, value);
        this.pos += 2;
      }
      writeI16(value) {
        this.ensureBufferSizeToWrite(2);
        this.view.setInt16(this.pos, value);
        this.pos += 2;
      }
      writeU32(value) {
        this.ensureBufferSizeToWrite(4);
        this.view.setUint32(this.pos, value);
        this.pos += 4;
      }
      writeI32(value) {
        this.ensureBufferSizeToWrite(4);
        this.view.setInt32(this.pos, value);
        this.pos += 4;
      }
      writeF32(value) {
        this.ensureBufferSizeToWrite(4);
        this.view.setFloat32(this.pos, value);
        this.pos += 4;
      }
      writeF64(value) {
        this.ensureBufferSizeToWrite(8);
        this.view.setFloat64(this.pos, value);
        this.pos += 8;
      }
      writeU64(value) {
        this.ensureBufferSizeToWrite(8);
        (0, int_ts_1.setUint64)(this.view, this.pos, value);
        this.pos += 8;
      }
      writeI64(value) {
        this.ensureBufferSizeToWrite(8);
        (0, int_ts_1.setInt64)(this.view, this.pos, value);
        this.pos += 8;
      }
      writeBigUint64(value) {
        this.ensureBufferSizeToWrite(8);
        this.view.setBigUint64(this.pos, value);
        this.pos += 8;
      }
      writeBigInt64(value) {
        this.ensureBufferSizeToWrite(8);
        this.view.setBigInt64(this.pos, value);
        this.pos += 8;
      }
    };
    exports.Encoder = Encoder;
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/encode.cjs
var require_encode = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/encode.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.encode = encode;
    var Encoder_ts_1 = require_Encoder();
    function encode(value, options) {
      const encoder = new Encoder_ts_1.Encoder(options);
      return encoder.encodeSharedRef(value);
    }
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/utils/prettyByte.cjs
var require_prettyByte = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/utils/prettyByte.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.prettyByte = prettyByte;
    function prettyByte(byte) {
      return `${byte < 0 ? "-" : ""}0x${Math.abs(byte).toString(16).padStart(2, "0")}`;
    }
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/CachedKeyDecoder.cjs
var require_CachedKeyDecoder = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/CachedKeyDecoder.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.CachedKeyDecoder = void 0;
    var utf8_ts_1 = require_utf8();
    var DEFAULT_MAX_KEY_LENGTH = 16;
    var DEFAULT_MAX_LENGTH_PER_KEY = 16;
    var CachedKeyDecoder = class {
      hit = 0;
      miss = 0;
      caches;
      maxKeyLength;
      maxLengthPerKey;
      constructor(maxKeyLength = DEFAULT_MAX_KEY_LENGTH, maxLengthPerKey = DEFAULT_MAX_LENGTH_PER_KEY) {
        this.maxKeyLength = maxKeyLength;
        this.maxLengthPerKey = maxLengthPerKey;
        this.caches = [];
        for (let i = 0; i < this.maxKeyLength; i++) {
          this.caches.push([]);
        }
      }
      canBeCached(byteLength) {
        return byteLength > 0 && byteLength <= this.maxKeyLength;
      }
      find(bytes, inputOffset, byteLength) {
        const records = this.caches[byteLength - 1];
        FIND_CHUNK: for (const record of records) {
          const recordBytes = record.bytes;
          for (let j = 0; j < byteLength; j++) {
            if (recordBytes[j] !== bytes[inputOffset + j]) {
              continue FIND_CHUNK;
            }
          }
          return record.str;
        }
        return null;
      }
      store(bytes, value) {
        const records = this.caches[bytes.length - 1];
        const record = { bytes, str: value };
        if (records.length >= this.maxLengthPerKey) {
          records[Math.random() * records.length | 0] = record;
        } else {
          records.push(record);
        }
      }
      decode(bytes, inputOffset, byteLength) {
        const cachedValue = this.find(bytes, inputOffset, byteLength);
        if (cachedValue != null) {
          this.hit++;
          return cachedValue;
        }
        this.miss++;
        const str = (0, utf8_ts_1.utf8DecodeJs)(bytes, inputOffset, byteLength);
        const slicedCopyOfBytes = Uint8Array.prototype.slice.call(bytes, inputOffset, inputOffset + byteLength);
        this.store(slicedCopyOfBytes, str);
        return str;
      }
    };
    exports.CachedKeyDecoder = CachedKeyDecoder;
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/Decoder.cjs
var require_Decoder = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/Decoder.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.Decoder = void 0;
    var prettyByte_ts_1 = require_prettyByte();
    var ExtensionCodec_ts_1 = require_ExtensionCodec();
    var int_ts_1 = require_int();
    var utf8_ts_1 = require_utf8();
    var typedArrays_ts_1 = require_typedArrays();
    var CachedKeyDecoder_ts_1 = require_CachedKeyDecoder();
    var DecodeError_ts_1 = require_DecodeError();
    var STATE_ARRAY = "array";
    var STATE_MAP_KEY = "map_key";
    var STATE_MAP_VALUE = "map_value";
    var mapKeyConverter = (key) => {
      if (typeof key === "string" || typeof key === "number") {
        return key;
      }
      throw new DecodeError_ts_1.DecodeError("The type of key must be string or number but " + typeof key);
    };
    var StackPool = class {
      stack = [];
      stackHeadPosition = -1;
      get length() {
        return this.stackHeadPosition + 1;
      }
      top() {
        return this.stack[this.stackHeadPosition];
      }
      pushArrayState(size) {
        const state = this.getUninitializedStateFromPool();
        state.type = STATE_ARRAY;
        state.position = 0;
        state.size = size;
        state.array = new Array(size);
      }
      pushMapState(size) {
        const state = this.getUninitializedStateFromPool();
        state.type = STATE_MAP_KEY;
        state.readCount = 0;
        state.size = size;
        state.map = {};
      }
      getUninitializedStateFromPool() {
        this.stackHeadPosition++;
        if (this.stackHeadPosition === this.stack.length) {
          const partialState = {
            type: void 0,
            size: 0,
            array: void 0,
            position: 0,
            readCount: 0,
            map: void 0,
            key: null
          };
          this.stack.push(partialState);
        }
        return this.stack[this.stackHeadPosition];
      }
      release(state) {
        const topStackState = this.stack[this.stackHeadPosition];
        if (topStackState !== state) {
          throw new Error("Invalid stack state. Released state is not on top of the stack.");
        }
        if (state.type === STATE_ARRAY) {
          const partialState = state;
          partialState.size = 0;
          partialState.array = void 0;
          partialState.position = 0;
          partialState.type = void 0;
        }
        if (state.type === STATE_MAP_KEY || state.type === STATE_MAP_VALUE) {
          const partialState = state;
          partialState.size = 0;
          partialState.map = void 0;
          partialState.readCount = 0;
          partialState.type = void 0;
        }
        this.stackHeadPosition--;
      }
      reset() {
        this.stack.length = 0;
        this.stackHeadPosition = -1;
      }
    };
    var HEAD_BYTE_REQUIRED = -1;
    var EMPTY_VIEW = new DataView(new ArrayBuffer(0));
    var EMPTY_BYTES = new Uint8Array(EMPTY_VIEW.buffer);
    try {
      EMPTY_VIEW.getInt8(0);
    } catch (e) {
      if (!(e instanceof RangeError)) {
        throw new Error("This module is not supported in the current JavaScript engine because DataView does not throw RangeError on out-of-bounds access");
      }
    }
    var MORE_DATA = new RangeError("Insufficient data");
    var sharedCachedKeyDecoder = new CachedKeyDecoder_ts_1.CachedKeyDecoder();
    var Decoder = class _Decoder {
      extensionCodec;
      context;
      useBigInt64;
      rawStrings;
      maxStrLength;
      maxBinLength;
      maxArrayLength;
      maxMapLength;
      maxExtLength;
      keyDecoder;
      mapKeyConverter;
      totalPos = 0;
      pos = 0;
      view = EMPTY_VIEW;
      bytes = EMPTY_BYTES;
      headByte = HEAD_BYTE_REQUIRED;
      stack = new StackPool();
      entered = false;
      constructor(options) {
        this.extensionCodec = options?.extensionCodec ?? ExtensionCodec_ts_1.ExtensionCodec.defaultCodec;
        this.context = options?.context;
        this.useBigInt64 = options?.useBigInt64 ?? false;
        this.rawStrings = options?.rawStrings ?? false;
        this.maxStrLength = options?.maxStrLength ?? int_ts_1.UINT32_MAX;
        this.maxBinLength = options?.maxBinLength ?? int_ts_1.UINT32_MAX;
        this.maxArrayLength = options?.maxArrayLength ?? int_ts_1.UINT32_MAX;
        this.maxMapLength = options?.maxMapLength ?? int_ts_1.UINT32_MAX;
        this.maxExtLength = options?.maxExtLength ?? int_ts_1.UINT32_MAX;
        this.keyDecoder = options?.keyDecoder !== void 0 ? options.keyDecoder : sharedCachedKeyDecoder;
        this.mapKeyConverter = options?.mapKeyConverter ?? mapKeyConverter;
      }
      clone() {
        return new _Decoder({
          extensionCodec: this.extensionCodec,
          context: this.context,
          useBigInt64: this.useBigInt64,
          rawStrings: this.rawStrings,
          maxStrLength: this.maxStrLength,
          maxBinLength: this.maxBinLength,
          maxArrayLength: this.maxArrayLength,
          maxMapLength: this.maxMapLength,
          maxExtLength: this.maxExtLength,
          keyDecoder: this.keyDecoder
        });
      }
      reinitializeState() {
        this.totalPos = 0;
        this.headByte = HEAD_BYTE_REQUIRED;
        this.stack.reset();
      }
      setBuffer(buffer) {
        const bytes = (0, typedArrays_ts_1.ensureUint8Array)(buffer);
        this.bytes = bytes;
        this.view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
        this.pos = 0;
      }
      appendBuffer(buffer) {
        if (this.headByte === HEAD_BYTE_REQUIRED && !this.hasRemaining(1)) {
          this.setBuffer(buffer);
        } else {
          const remainingData = this.bytes.subarray(this.pos);
          const newData = (0, typedArrays_ts_1.ensureUint8Array)(buffer);
          const newBuffer = new Uint8Array(remainingData.length + newData.length);
          newBuffer.set(remainingData);
          newBuffer.set(newData, remainingData.length);
          this.setBuffer(newBuffer);
        }
      }
      hasRemaining(size) {
        return this.view.byteLength - this.pos >= size;
      }
      createExtraByteError(posToShow) {
        const { view, pos } = this;
        return new RangeError(`Extra ${view.byteLength - pos} of ${view.byteLength} byte(s) found at buffer[${posToShow}]`);
      }
      /**
       * @throws {@link DecodeError}
       * @throws {@link RangeError}
       */
      decode(buffer) {
        if (this.entered) {
          const instance = this.clone();
          return instance.decode(buffer);
        }
        try {
          this.entered = true;
          this.reinitializeState();
          this.setBuffer(buffer);
          const object = this.doDecodeSync();
          if (this.hasRemaining(1)) {
            throw this.createExtraByteError(this.pos);
          }
          return object;
        } finally {
          this.entered = false;
        }
      }
      *decodeMulti(buffer) {
        if (this.entered) {
          const instance = this.clone();
          yield* instance.decodeMulti(buffer);
          return;
        }
        try {
          this.entered = true;
          this.reinitializeState();
          this.setBuffer(buffer);
          while (this.hasRemaining(1)) {
            yield this.doDecodeSync();
          }
        } finally {
          this.entered = false;
        }
      }
      async decodeAsync(stream) {
        if (this.entered) {
          const instance = this.clone();
          return instance.decodeAsync(stream);
        }
        try {
          this.entered = true;
          let decoded = false;
          let object;
          for await (const buffer of stream) {
            if (decoded) {
              this.entered = false;
              throw this.createExtraByteError(this.totalPos);
            }
            this.appendBuffer(buffer);
            try {
              object = this.doDecodeSync();
              decoded = true;
            } catch (e) {
              if (!(e instanceof RangeError)) {
                throw e;
              }
            }
            this.totalPos += this.pos;
          }
          if (decoded) {
            if (this.hasRemaining(1)) {
              throw this.createExtraByteError(this.totalPos);
            }
            return object;
          }
          const { headByte, pos, totalPos } = this;
          throw new RangeError(`Insufficient data in parsing ${(0, prettyByte_ts_1.prettyByte)(headByte)} at ${totalPos} (${pos} in the current buffer)`);
        } finally {
          this.entered = false;
        }
      }
      decodeArrayStream(stream) {
        return this.decodeMultiAsync(stream, true);
      }
      decodeStream(stream) {
        return this.decodeMultiAsync(stream, false);
      }
      async *decodeMultiAsync(stream, isArray) {
        if (this.entered) {
          const instance = this.clone();
          yield* instance.decodeMultiAsync(stream, isArray);
          return;
        }
        try {
          this.entered = true;
          let isArrayHeaderRequired = isArray;
          let arrayItemsLeft = -1;
          for await (const buffer of stream) {
            if (isArray && arrayItemsLeft === 0) {
              throw this.createExtraByteError(this.totalPos);
            }
            this.appendBuffer(buffer);
            if (isArrayHeaderRequired) {
              arrayItemsLeft = this.readArraySize();
              isArrayHeaderRequired = false;
              this.complete();
            }
            try {
              while (true) {
                yield this.doDecodeSync();
                if (--arrayItemsLeft === 0) {
                  break;
                }
              }
            } catch (e) {
              if (!(e instanceof RangeError)) {
                throw e;
              }
            }
            this.totalPos += this.pos;
          }
        } finally {
          this.entered = false;
        }
      }
      doDecodeSync() {
        DECODE: while (true) {
          const headByte = this.readHeadByte();
          let object;
          if (headByte >= 224) {
            object = headByte - 256;
          } else if (headByte < 192) {
            if (headByte < 128) {
              object = headByte;
            } else if (headByte < 144) {
              const size = headByte - 128;
              if (size !== 0) {
                this.pushMapState(size);
                this.complete();
                continue DECODE;
              } else {
                object = {};
              }
            } else if (headByte < 160) {
              const size = headByte - 144;
              if (size !== 0) {
                this.pushArrayState(size);
                this.complete();
                continue DECODE;
              } else {
                object = [];
              }
            } else {
              const byteLength = headByte - 160;
              object = this.decodeString(byteLength, 0);
            }
          } else if (headByte === 192) {
            object = null;
          } else if (headByte === 194) {
            object = false;
          } else if (headByte === 195) {
            object = true;
          } else if (headByte === 202) {
            object = this.readF32();
          } else if (headByte === 203) {
            object = this.readF64();
          } else if (headByte === 204) {
            object = this.readU8();
          } else if (headByte === 205) {
            object = this.readU16();
          } else if (headByte === 206) {
            object = this.readU32();
          } else if (headByte === 207) {
            if (this.useBigInt64) {
              object = this.readU64AsBigInt();
            } else {
              object = this.readU64();
            }
          } else if (headByte === 208) {
            object = this.readI8();
          } else if (headByte === 209) {
            object = this.readI16();
          } else if (headByte === 210) {
            object = this.readI32();
          } else if (headByte === 211) {
            if (this.useBigInt64) {
              object = this.readI64AsBigInt();
            } else {
              object = this.readI64();
            }
          } else if (headByte === 217) {
            const byteLength = this.lookU8();
            object = this.decodeString(byteLength, 1);
          } else if (headByte === 218) {
            const byteLength = this.lookU16();
            object = this.decodeString(byteLength, 2);
          } else if (headByte === 219) {
            const byteLength = this.lookU32();
            object = this.decodeString(byteLength, 4);
          } else if (headByte === 220) {
            const size = this.readU16();
            if (size !== 0) {
              this.pushArrayState(size);
              this.complete();
              continue DECODE;
            } else {
              object = [];
            }
          } else if (headByte === 221) {
            const size = this.readU32();
            if (size !== 0) {
              this.pushArrayState(size);
              this.complete();
              continue DECODE;
            } else {
              object = [];
            }
          } else if (headByte === 222) {
            const size = this.readU16();
            if (size !== 0) {
              this.pushMapState(size);
              this.complete();
              continue DECODE;
            } else {
              object = {};
            }
          } else if (headByte === 223) {
            const size = this.readU32();
            if (size !== 0) {
              this.pushMapState(size);
              this.complete();
              continue DECODE;
            } else {
              object = {};
            }
          } else if (headByte === 196) {
            const size = this.lookU8();
            object = this.decodeBinary(size, 1);
          } else if (headByte === 197) {
            const size = this.lookU16();
            object = this.decodeBinary(size, 2);
          } else if (headByte === 198) {
            const size = this.lookU32();
            object = this.decodeBinary(size, 4);
          } else if (headByte === 212) {
            object = this.decodeExtension(1, 0);
          } else if (headByte === 213) {
            object = this.decodeExtension(2, 0);
          } else if (headByte === 214) {
            object = this.decodeExtension(4, 0);
          } else if (headByte === 215) {
            object = this.decodeExtension(8, 0);
          } else if (headByte === 216) {
            object = this.decodeExtension(16, 0);
          } else if (headByte === 199) {
            const size = this.lookU8();
            object = this.decodeExtension(size, 1);
          } else if (headByte === 200) {
            const size = this.lookU16();
            object = this.decodeExtension(size, 2);
          } else if (headByte === 201) {
            const size = this.lookU32();
            object = this.decodeExtension(size, 4);
          } else {
            throw new DecodeError_ts_1.DecodeError(`Unrecognized type byte: ${(0, prettyByte_ts_1.prettyByte)(headByte)}`);
          }
          this.complete();
          const stack = this.stack;
          while (stack.length > 0) {
            const state = stack.top();
            if (state.type === STATE_ARRAY) {
              state.array[state.position] = object;
              state.position++;
              if (state.position === state.size) {
                object = state.array;
                stack.release(state);
              } else {
                continue DECODE;
              }
            } else if (state.type === STATE_MAP_KEY) {
              if (object === "__proto__") {
                throw new DecodeError_ts_1.DecodeError("The key __proto__ is not allowed");
              }
              state.key = this.mapKeyConverter(object);
              state.type = STATE_MAP_VALUE;
              continue DECODE;
            } else {
              state.map[state.key] = object;
              state.readCount++;
              if (state.readCount === state.size) {
                object = state.map;
                stack.release(state);
              } else {
                state.key = null;
                state.type = STATE_MAP_KEY;
                continue DECODE;
              }
            }
          }
          return object;
        }
      }
      readHeadByte() {
        if (this.headByte === HEAD_BYTE_REQUIRED) {
          this.headByte = this.readU8();
        }
        return this.headByte;
      }
      complete() {
        this.headByte = HEAD_BYTE_REQUIRED;
      }
      readArraySize() {
        const headByte = this.readHeadByte();
        switch (headByte) {
          case 220:
            return this.readU16();
          case 221:
            return this.readU32();
          default: {
            if (headByte < 160) {
              return headByte - 144;
            } else {
              throw new DecodeError_ts_1.DecodeError(`Unrecognized array type byte: ${(0, prettyByte_ts_1.prettyByte)(headByte)}`);
            }
          }
        }
      }
      pushMapState(size) {
        if (size > this.maxMapLength) {
          throw new DecodeError_ts_1.DecodeError(`Max length exceeded: map length (${size}) > maxMapLengthLength (${this.maxMapLength})`);
        }
        this.stack.pushMapState(size);
      }
      pushArrayState(size) {
        if (size > this.maxArrayLength) {
          throw new DecodeError_ts_1.DecodeError(`Max length exceeded: array length (${size}) > maxArrayLength (${this.maxArrayLength})`);
        }
        this.stack.pushArrayState(size);
      }
      decodeString(byteLength, headerOffset) {
        if (!this.rawStrings || this.stateIsMapKey()) {
          return this.decodeUtf8String(byteLength, headerOffset);
        }
        return this.decodeBinary(byteLength, headerOffset);
      }
      /**
       * @throws {@link RangeError}
       */
      decodeUtf8String(byteLength, headerOffset) {
        if (byteLength > this.maxStrLength) {
          throw new DecodeError_ts_1.DecodeError(`Max length exceeded: UTF-8 byte length (${byteLength}) > maxStrLength (${this.maxStrLength})`);
        }
        if (this.bytes.byteLength < this.pos + headerOffset + byteLength) {
          throw MORE_DATA;
        }
        const offset = this.pos + headerOffset;
        let object;
        if (this.stateIsMapKey() && this.keyDecoder?.canBeCached(byteLength)) {
          object = this.keyDecoder.decode(this.bytes, offset, byteLength);
        } else {
          object = (0, utf8_ts_1.utf8Decode)(this.bytes, offset, byteLength);
        }
        this.pos += headerOffset + byteLength;
        return object;
      }
      stateIsMapKey() {
        if (this.stack.length > 0) {
          const state = this.stack.top();
          return state.type === STATE_MAP_KEY;
        }
        return false;
      }
      /**
       * @throws {@link RangeError}
       */
      decodeBinary(byteLength, headOffset) {
        if (byteLength > this.maxBinLength) {
          throw new DecodeError_ts_1.DecodeError(`Max length exceeded: bin length (${byteLength}) > maxBinLength (${this.maxBinLength})`);
        }
        if (!this.hasRemaining(byteLength + headOffset)) {
          throw MORE_DATA;
        }
        const offset = this.pos + headOffset;
        const object = this.bytes.subarray(offset, offset + byteLength);
        this.pos += headOffset + byteLength;
        return object;
      }
      decodeExtension(size, headOffset) {
        if (size > this.maxExtLength) {
          throw new DecodeError_ts_1.DecodeError(`Max length exceeded: ext length (${size}) > maxExtLength (${this.maxExtLength})`);
        }
        const extType = this.view.getInt8(this.pos + headOffset);
        const data = this.decodeBinary(
          size,
          headOffset + 1
          /* extType */
        );
        return this.extensionCodec.decode(data, extType, this.context);
      }
      lookU8() {
        return this.view.getUint8(this.pos);
      }
      lookU16() {
        return this.view.getUint16(this.pos);
      }
      lookU32() {
        return this.view.getUint32(this.pos);
      }
      readU8() {
        const value = this.view.getUint8(this.pos);
        this.pos++;
        return value;
      }
      readI8() {
        const value = this.view.getInt8(this.pos);
        this.pos++;
        return value;
      }
      readU16() {
        const value = this.view.getUint16(this.pos);
        this.pos += 2;
        return value;
      }
      readI16() {
        const value = this.view.getInt16(this.pos);
        this.pos += 2;
        return value;
      }
      readU32() {
        const value = this.view.getUint32(this.pos);
        this.pos += 4;
        return value;
      }
      readI32() {
        const value = this.view.getInt32(this.pos);
        this.pos += 4;
        return value;
      }
      readU64() {
        const value = (0, int_ts_1.getUint64)(this.view, this.pos);
        this.pos += 8;
        return value;
      }
      readI64() {
        const value = (0, int_ts_1.getInt64)(this.view, this.pos);
        this.pos += 8;
        return value;
      }
      readU64AsBigInt() {
        const value = this.view.getBigUint64(this.pos);
        this.pos += 8;
        return value;
      }
      readI64AsBigInt() {
        const value = this.view.getBigInt64(this.pos);
        this.pos += 8;
        return value;
      }
      readF32() {
        const value = this.view.getFloat32(this.pos);
        this.pos += 4;
        return value;
      }
      readF64() {
        const value = this.view.getFloat64(this.pos);
        this.pos += 8;
        return value;
      }
    };
    exports.Decoder = Decoder;
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/decode.cjs
var require_decode = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/decode.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.decode = decode;
    exports.decodeMulti = decodeMulti;
    var Decoder_ts_1 = require_Decoder();
    function decode(buffer, options) {
      const decoder = new Decoder_ts_1.Decoder(options);
      return decoder.decode(buffer);
    }
    function decodeMulti(buffer, options) {
      const decoder = new Decoder_ts_1.Decoder(options);
      return decoder.decodeMulti(buffer);
    }
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/utils/stream.cjs
var require_stream = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/utils/stream.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.isAsyncIterable = isAsyncIterable;
    exports.asyncIterableFromStream = asyncIterableFromStream;
    exports.ensureAsyncIterable = ensureAsyncIterable;
    function isAsyncIterable(object) {
      return object[Symbol.asyncIterator] != null;
    }
    async function* asyncIterableFromStream(stream) {
      const reader = stream.getReader();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            return;
          }
          yield value;
        }
      } finally {
        reader.releaseLock();
      }
    }
    function ensureAsyncIterable(streamLike) {
      if (isAsyncIterable(streamLike)) {
        return streamLike;
      } else {
        return asyncIterableFromStream(streamLike);
      }
    }
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/decodeAsync.cjs
var require_decodeAsync = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/decodeAsync.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.decodeAsync = decodeAsync;
    exports.decodeArrayStream = decodeArrayStream;
    exports.decodeMultiStream = decodeMultiStream;
    var Decoder_ts_1 = require_Decoder();
    var stream_ts_1 = require_stream();
    async function decodeAsync(streamLike, options) {
      const stream = (0, stream_ts_1.ensureAsyncIterable)(streamLike);
      const decoder = new Decoder_ts_1.Decoder(options);
      return decoder.decodeAsync(stream);
    }
    function decodeArrayStream(streamLike, options) {
      const stream = (0, stream_ts_1.ensureAsyncIterable)(streamLike);
      const decoder = new Decoder_ts_1.Decoder(options);
      return decoder.decodeArrayStream(stream);
    }
    function decodeMultiStream(streamLike, options) {
      const stream = (0, stream_ts_1.ensureAsyncIterable)(streamLike);
      const decoder = new Decoder_ts_1.Decoder(options);
      return decoder.decodeStream(stream);
    }
  }
});

// node_modules/@msgpack/msgpack/dist.cjs/index.cjs
var require_dist2 = __commonJS({
  "node_modules/@msgpack/msgpack/dist.cjs/index.cjs"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.decodeTimestampExtension = exports.encodeTimestampExtension = exports.decodeTimestampToTimeSpec = exports.encodeTimeSpecToTimestamp = exports.encodeDateToTimeSpec = exports.EXT_TIMESTAMP = exports.ExtData = exports.ExtensionCodec = exports.Encoder = exports.DecodeError = exports.Decoder = exports.decodeMultiStream = exports.decodeArrayStream = exports.decodeAsync = exports.decodeMulti = exports.decode = exports.encode = void 0;
    var encode_ts_1 = require_encode();
    Object.defineProperty(exports, "encode", { enumerable: true, get: function() {
      return encode_ts_1.encode;
    } });
    var decode_ts_1 = require_decode();
    Object.defineProperty(exports, "decode", { enumerable: true, get: function() {
      return decode_ts_1.decode;
    } });
    Object.defineProperty(exports, "decodeMulti", { enumerable: true, get: function() {
      return decode_ts_1.decodeMulti;
    } });
    var decodeAsync_ts_1 = require_decodeAsync();
    Object.defineProperty(exports, "decodeAsync", { enumerable: true, get: function() {
      return decodeAsync_ts_1.decodeAsync;
    } });
    Object.defineProperty(exports, "decodeArrayStream", { enumerable: true, get: function() {
      return decodeAsync_ts_1.decodeArrayStream;
    } });
    Object.defineProperty(exports, "decodeMultiStream", { enumerable: true, get: function() {
      return decodeAsync_ts_1.decodeMultiStream;
    } });
    var Decoder_ts_1 = require_Decoder();
    Object.defineProperty(exports, "Decoder", { enumerable: true, get: function() {
      return Decoder_ts_1.Decoder;
    } });
    var DecodeError_ts_1 = require_DecodeError();
    Object.defineProperty(exports, "DecodeError", { enumerable: true, get: function() {
      return DecodeError_ts_1.DecodeError;
    } });
    var Encoder_ts_1 = require_Encoder();
    Object.defineProperty(exports, "Encoder", { enumerable: true, get: function() {
      return Encoder_ts_1.Encoder;
    } });
    var ExtensionCodec_ts_1 = require_ExtensionCodec();
    Object.defineProperty(exports, "ExtensionCodec", { enumerable: true, get: function() {
      return ExtensionCodec_ts_1.ExtensionCodec;
    } });
    var ExtData_ts_1 = require_ExtData();
    Object.defineProperty(exports, "ExtData", { enumerable: true, get: function() {
      return ExtData_ts_1.ExtData;
    } });
    var timestamp_ts_1 = require_timestamp();
    Object.defineProperty(exports, "EXT_TIMESTAMP", { enumerable: true, get: function() {
      return timestamp_ts_1.EXT_TIMESTAMP;
    } });
    Object.defineProperty(exports, "encodeDateToTimeSpec", { enumerable: true, get: function() {
      return timestamp_ts_1.encodeDateToTimeSpec;
    } });
    Object.defineProperty(exports, "encodeTimeSpecToTimestamp", { enumerable: true, get: function() {
      return timestamp_ts_1.encodeTimeSpecToTimestamp;
    } });
    Object.defineProperty(exports, "decodeTimestampToTimeSpec", { enumerable: true, get: function() {
      return timestamp_ts_1.decodeTimestampToTimeSpec;
    } });
    Object.defineProperty(exports, "encodeTimestampExtension", { enumerable: true, get: function() {
      return timestamp_ts_1.encodeTimestampExtension;
    } });
    Object.defineProperty(exports, "decodeTimestampExtension", { enumerable: true, get: function() {
      return timestamp_ts_1.decodeTimestampExtension;
    } });
  }
});

// node_modules/robot3/dist/machine.js
var require_machine = __commonJS({
  "node_modules/robot3/dist/machine.js"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    function valueEnumerable(value) {
      return { enumerable: true, value };
    }
    function valueEnumerableWritable(value) {
      return { enumerable: true, writable: true, value };
    }
    var d = {};
    var truthy = () => true;
    var empty = () => ({});
    var identity = (a) => a;
    var callBoth = (par, fn, self, args) => par.apply(self, args) && fn.apply(self, args);
    var callForward = (par, fn, self, [a, b]) => fn.call(self, par.call(self, a, b), b);
    var create = (a, b) => Object.freeze(Object.create(a, b));
    function stack(fns, def, caller) {
      return fns.reduce((par, fn) => {
        return function(...args) {
          return caller(par, fn, this, args);
        };
      }, def);
    }
    function fnType(fn) {
      return create(this, { fn: valueEnumerable(fn) });
    }
    var reduceType = {};
    var reduce = fnType.bind(reduceType);
    var action = (fn) => reduce((ctx, ev) => !!~fn(ctx, ev) && ctx);
    var guardType = {};
    var guard = fnType.bind(guardType);
    function filter(Type, arr) {
      return arr.filter((value) => Type.isPrototypeOf(value));
    }
    function makeTransition(from, to, ...args) {
      let guards = stack(filter(guardType, args).map((t) => t.fn), truthy, callBoth);
      let reducers = stack(filter(reduceType, args).map((t) => t.fn), identity, callForward);
      return create(this, {
        from: valueEnumerable(from),
        to: valueEnumerable(to),
        guards: valueEnumerable(guards),
        reducers: valueEnumerable(reducers)
      });
    }
    var transitionType = {};
    var immediateType = {};
    var transition = makeTransition.bind(transitionType);
    var immediate = makeTransition.bind(immediateType, null);
    function enterImmediate(machine2, service2, event) {
      return transitionTo(service2, machine2, event, this.immediates) || machine2;
    }
    function transitionsToMap(transitions) {
      let m = /* @__PURE__ */ new Map();
      for (let t of transitions) {
        if (!m.has(t.from)) m.set(t.from, []);
        m.get(t.from).push(t);
      }
      return m;
    }
    var stateType = { enter: identity };
    function state(...args) {
      let transitions = filter(transitionType, args);
      let immediates = filter(immediateType, args);
      let desc = {
        final: valueEnumerable(args.length === 0),
        transitions: valueEnumerable(transitionsToMap(transitions))
      };
      if (immediates.length) {
        desc.immediates = valueEnumerable(immediates);
        desc.enter = valueEnumerable(enterImmediate);
      }
      return create(stateType, desc);
    }
    var invokeFnType = {
      enter(machine2, service2, event) {
        let rn = this.fn.call(service2, service2.context, event);
        if (machine.isPrototypeOf(rn))
          return create(invokeMachineType, {
            machine: valueEnumerable(rn),
            transitions: valueEnumerable(this.transitions)
          }).enter(machine2, service2, event);
        rn.then((data) => service2.send({ type: "done", data })).catch((error) => service2.send({ type: "error", error }));
        return machine2;
      }
    };
    var invokeMachineType = {
      enter(machine2, service2, event) {
        service2.child = interpret(this.machine, (s) => {
          service2.onChange(s);
          if (service2.child == s && s.machine.state.value.final) {
            delete service2.child;
            service2.send({ type: "done", data: s.context });
          }
        }, service2.context, event);
        if (service2.child.machine.state.value.final) {
          let data = service2.child.context;
          delete service2.child;
          return transitionTo(service2, machine2, { type: "done", data }, this.transitions.get("done"));
        }
        return machine2;
      }
    };
    function invoke(fn, ...transitions) {
      let t = valueEnumerable(transitionsToMap(transitions));
      return machine.isPrototypeOf(fn) ? create(invokeMachineType, {
        machine: valueEnumerable(fn),
        transitions: t
      }) : create(invokeFnType, {
        fn: valueEnumerable(fn),
        transitions: t
      });
    }
    var machine = {
      get state() {
        return {
          name: this.current,
          value: this.states[this.current]
        };
      }
    };
    function createMachine(current, states, contextFn = empty) {
      if (typeof current !== "string") {
        contextFn = states || empty;
        states = current;
        current = Object.keys(states)[0];
      }
      if (d._create) d._create(current, states);
      return create(machine, {
        context: valueEnumerable(contextFn),
        current: valueEnumerable(current),
        states: valueEnumerable(states)
      });
    }
    function transitionTo(service2, machine2, fromEvent, candidates) {
      let { context } = service2;
      for (let { to, guards, reducers } of candidates) {
        if (guards(context, fromEvent)) {
          service2.context = reducers.call(service2, context, fromEvent);
          let original = machine2.original || machine2;
          let newMachine = create(original, {
            current: valueEnumerable(to),
            original: { value: original }
          });
          if (d._onEnter) d._onEnter(machine2, to, service2.context, context, fromEvent);
          let state2 = newMachine.state.value;
          return state2.enter(newMachine, service2, fromEvent);
        }
      }
    }
    function send(service2, event) {
      let eventName = event.type || event;
      let { machine: machine2 } = service2;
      let { value: state2, name: currentStateName } = machine2.state;
      if (state2.transitions.has(eventName)) {
        return transitionTo(service2, machine2, event, state2.transitions.get(eventName)) || machine2;
      } else {
        if (d._send) d._send(eventName, currentStateName);
      }
      return machine2;
    }
    var service = {
      send(event) {
        this.machine = send(this, event);
        this.onChange(this);
      }
    };
    function interpret(machine2, onChange, initialContext, event) {
      let s = Object.create(service, {
        machine: valueEnumerableWritable(machine2),
        context: valueEnumerableWritable(machine2.context(initialContext, event)),
        onChange: valueEnumerable(onChange)
      });
      s.send = s.send.bind(s);
      s.machine = s.machine.state.value.enter(s.machine, s, event);
      return s;
    }
    exports.action = action;
    exports.createMachine = createMachine;
    exports.d = d;
    exports.guard = guard;
    exports.immediate = immediate;
    exports.interpret = interpret;
    exports.invoke = invoke;
    exports.reduce = reduce;
    exports.state = state;
    exports.transition = transition;
  }
});

// node_modules/@fal-ai/client/src/realtime/ice.js
var require_ice = __commonJS({
  "node_modules/@fal-ai/client/src/realtime/ice.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.DEFAULT_ICE_QUIET_PERIOD_MS = exports.DEFAULT_ICE_TIMEOUT_MS = void 0;
    exports.countTurnServers = countTurnServers;
    exports.hasTurnServer = hasTurnServer;
    exports.parseIceCandidateType = parseIceCandidateType;
    exports.gatherIceCandidates = gatherIceCandidates;
    exports.DEFAULT_ICE_TIMEOUT_MS = 12e3;
    exports.DEFAULT_ICE_QUIET_PERIOD_MS = 1250;
    function countTurnServers(iceServers) {
      return iceServers.filter((server) => {
        const urls = Array.isArray(server.urls) ? server.urls : [server.urls];
        return urls.some((url) => /^turns?:/i.test(url));
      }).length;
    }
    function hasTurnServer(iceServers) {
      return countTurnServers(iceServers) > 0;
    }
    function parseIceCandidateType(candidate) {
      var _a;
      const match = candidate.match(/(?:^|\s)typ\s+(host|srflx|relay)(?:\s|$)/);
      return (_a = match === null || match === void 0 ? void 0 : match[1]) !== null && _a !== void 0 ? _a : null;
    }
    function gatherIceCandidates(pc_1) {
      return __awaiter(this, arguments, void 0, function* (pc, options = {}) {
        var _a;
        const { iceServers = [], iceTransportPolicy = "all", timeoutMs = exports.DEFAULT_ICE_TIMEOUT_MS, quietPeriodMs = exports.DEFAULT_ICE_QUIET_PERIOD_MS, signal, onProgress } = options;
        const abortReason = () => {
          var _a2;
          return (_a2 = signal === null || signal === void 0 ? void 0 : signal.reason) !== null && _a2 !== void 0 ? _a2 : new DOMException("ICE gathering aborted", "AbortError");
        };
        if (signal === null || signal === void 0 ? void 0 : signal.aborted)
          throw abortReason();
        const counts = { host: 0, srflx: 0, relay: 0 };
        const snapshot = (state) => Object.assign(Object.assign({}, counts), { state });
        const sdp = (_a = pc.localDescription) === null || _a === void 0 ? void 0 : _a.sdp;
        if (sdp) {
          for (const line of sdp.split(/\r?\n/)) {
            if (line.startsWith("a=candidate:")) {
              const type = parseIceCandidateType(line.slice(2));
              if (type)
                counts[type] += 1;
            }
          }
        }
        if (pc.iceGatheringState === "complete") {
          const done = snapshot("complete");
          try {
            onProgress === null || onProgress === void 0 ? void 0 : onProgress(done);
          } catch (_b) {
          }
          return done;
        }
        return new Promise((resolve, reject) => {
          let settled = false;
          let quiet = null;
          const requireRelay = hasTurnServer(iceServers);
          const sufficient = () => iceTransportPolicy === "relay" ? counts.relay > 0 : requireRelay ? counts.relay > 0 : counts.srflx > 0;
          const removeWaiters = () => {
            clearTimeout(hardBound);
            if (quiet !== null)
              clearTimeout(quiet);
            pc.removeEventListener("icegatheringstatechange", onState);
            pc.removeEventListener("icecandidate", onCandidate);
            signal === null || signal === void 0 ? void 0 : signal.removeEventListener("abort", onAbort);
          };
          const finish = (state) => {
            if (settled)
              return;
            settled = true;
            removeWaiters();
            const done = snapshot(state);
            try {
              onProgress === null || onProgress === void 0 ? void 0 : onProgress(done);
            } catch (_a2) {
            }
            resolve(done);
          };
          const onAbort = () => {
            if (settled)
              return;
            settled = true;
            removeWaiters();
            reject(abortReason());
          };
          const onState = () => {
            if (pc.iceGatheringState === "complete")
              finish("complete");
          };
          const onCandidate = (event) => {
            const type = event.candidate ? parseIceCandidateType(event.candidate.candidate) : null;
            if (type)
              counts[type] += 1;
            if (quiet !== null)
              clearTimeout(quiet);
            if (sufficient())
              quiet = setTimeout(() => finish("sufficient"), quietPeriodMs);
          };
          const hardBound = setTimeout(() => finish("timeout"), timeoutMs);
          pc.addEventListener("icegatheringstatechange", onState);
          pc.addEventListener("icecandidate", onCandidate);
          signal === null || signal === void 0 ? void 0 : signal.addEventListener("abort", onAbort, { once: true });
          if (sufficient()) {
            quiet = setTimeout(() => finish("sufficient"), quietPeriodMs);
          }
          if (signal === null || signal === void 0 ? void 0 : signal.aborted)
            onAbort();
        });
      });
    }
  }
});

// node_modules/@fal-ai/client/src/realtime/protocol.js
var require_protocol = __commonJS({
  "node_modules/@fal-ai/client/src/realtime/protocol.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.WebSocketErrorCodes = exports.DEFAULT_THROTTLE_INTERVAL = void 0;
    exports.buildRealtimeUrl = buildRealtimeUrl;
    exports.realtimeTokenScope = realtimeTokenScope;
    exports.isUnauthorizedError = isUnauthorizedError;
    exports.isSuccessfulResult = isSuccessfulResult;
    exports.isFalErrorResult = isFalErrorResult;
    exports.decodeRealtimeMessage = decodeRealtimeMessage;
    exports.encodeRealtimeMessage = encodeRealtimeMessage;
    var msgpack_1 = require_dist2();
    var utils_1 = require_utils();
    exports.DEFAULT_THROTTLE_INTERVAL = 128;
    exports.WebSocketErrorCodes = {
      NORMAL_CLOSURE: 1e3,
      GOING_AWAY: 1001
    };
    function buildRealtimeUrl(app, { token, maxBuffering, path }) {
      var _a;
      if (maxBuffering !== void 0 && (maxBuffering < 1 || maxBuffering > 60)) {
        throw new Error("The `maxBuffering` must be between 1 and 60 (inclusive)");
      }
      const queryParams = new URLSearchParams({
        fal_jwt_token: token
      });
      if (maxBuffering !== void 0) {
        queryParams.set("max_buffering", maxBuffering.toFixed(0));
      }
      const appId = (0, utils_1.ensureEndpointIdFormat)(app);
      const resolvedPath = (_a = (0, utils_1.resolveEndpointPath)(app, path, "/realtime")) !== null && _a !== void 0 ? _a : "";
      return `wss://fal.run/${appId}${resolvedPath}?${queryParams.toString()}`;
    }
    function realtimeTokenScope(app, path) {
      var _a;
      if (/^[a-z][a-z\d+.-]*:\/\//i.test(app.trim())) {
        throw new Error('Realtime endpoints take an app id like "owner/app", not a URL \u2014 the socket address is derived from the id.');
      }
      return `${(0, utils_1.ensureEndpointIdFormat)(app)}${(_a = (0, utils_1.resolveEndpointPath)(app, path, "/realtime")) !== null && _a !== void 0 ? _a : ""}`;
    }
    function isUnauthorizedError(message) {
      return message["status"] === "error" && message["error"] === "Unauthorized";
    }
    function isSuccessfulResult(data) {
      return data.status !== "error" && data.type !== "x-fal-message" && !isFalErrorResult(data);
    }
    function isFalErrorResult(data) {
      return data.type === "x-fal-error";
    }
    function decodeRealtimeMessage(data) {
      return __awaiter(this, void 0, void 0, function* () {
        if (typeof data === "string") {
          return JSON.parse(data);
        }
        const toUint8Array = (value) => __awaiter(this, void 0, void 0, function* () {
          if (value instanceof Uint8Array) {
            return value;
          }
          if (value instanceof Blob) {
            return new Uint8Array(yield value.arrayBuffer());
          }
          return new Uint8Array(value);
        });
        if (data instanceof ArrayBuffer || data instanceof Uint8Array) {
          return (0, msgpack_1.decode)(yield toUint8Array(data));
        }
        if (data instanceof Blob) {
          return (0, msgpack_1.decode)(yield toUint8Array(data));
        }
        return data;
      });
    }
    function encodeRealtimeMessage(input) {
      if (input instanceof Uint8Array) {
        return input;
      }
      if (typeof input === "string") {
        return (0, msgpack_1.encode)(input);
      }
      return (0, msgpack_1.encode)(input);
    }
  }
});

// node_modules/@fal-ai/client/src/realtime.js
var require_realtime = __commonJS({
  "node_modules/@fal-ai/client/src/realtime.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.createRealtimeClient = createRealtimeClient;
    var msgpack_1 = require_dist2();
    var robot3_1 = require_machine();
    var auth_1 = require_auth();
    var ice_1 = require_ice();
    var protocol_1 = require_protocol();
    var response_1 = require_response();
    var runtime_1 = require_runtime();
    var utils_1 = require_utils();
    var FAL_SERVICE_HOSTS = /* @__PURE__ */ new Set(["wma.fal.run"]);
    function assertFalInfrastructureUrl(rawUrl) {
      let url;
      try {
        url = new URL(rawUrl);
      } catch (_a) {
        throw new Error("Realtime infrastructure fetch requires an absolute URL.");
      }
      const host = url.host.toLowerCase();
      const isFalInfrastructure = url.protocol === "https:" && (host === "fal.ai" || host.endsWith(".fal.ai") || FAL_SERVICE_HOSTS.has(host));
      if (!isFalInfrastructure) {
        throw new Error("Realtime infrastructure fetch is restricted to fal-operated HTTPS hosts.");
      }
    }
    var initialState = () => ({
      enqueuedMessage: void 0
    });
    function hasToken(context) {
      return context.token !== void 0;
    }
    function noToken(context) {
      return !hasToken(context);
    }
    function enqueueMessage(context, event) {
      return Object.assign(Object.assign({}, context), { enqueuedMessage: event.message });
    }
    function closeConnection(context) {
      if (context.websocket && context.websocket.readyState === WebSocket.OPEN) {
        context.websocket.close();
      }
      return Object.assign(Object.assign({}, context), { websocket: void 0 });
    }
    function sendMessage(context, event) {
      if (context.websocket && context.websocket.readyState === WebSocket.OPEN) {
        if (event.message instanceof Uint8Array) {
          context.websocket.send(event.message);
        } else if (typeof event.message === "string") {
          context.websocket.send(event.message);
        } else {
          context.websocket.send((0, msgpack_1.encode)(event.message));
        }
        return Object.assign(Object.assign({}, context), { enqueuedMessage: void 0 });
      }
      return Object.assign(Object.assign({}, context), { enqueuedMessage: event.message });
    }
    function expireToken(context) {
      return Object.assign(Object.assign({}, context), { token: void 0 });
    }
    function setToken(context, event) {
      return Object.assign(Object.assign({}, context), { token: event.token });
    }
    function connectionEstablished(context, event) {
      return Object.assign(Object.assign({}, context), { websocket: event.websocket });
    }
    var connectionStateMachine = (0, robot3_1.createMachine)("idle", {
      idle: (0, robot3_1.state)((0, robot3_1.transition)("send", "connecting", (0, robot3_1.reduce)(enqueueMessage)), (0, robot3_1.transition)("close", "idle", (0, robot3_1.reduce)(closeConnection))),
      connecting: (0, robot3_1.state)((0, robot3_1.transition)("connecting", "connecting"), (0, robot3_1.transition)("connected", "active", (0, robot3_1.reduce)(connectionEstablished)), (0, robot3_1.transition)("connectionClosed", "idle", (0, robot3_1.reduce)(closeConnection)), (0, robot3_1.transition)("send", "connecting", (0, robot3_1.reduce)(enqueueMessage)), (0, robot3_1.transition)("close", "idle", (0, robot3_1.reduce)(closeConnection)), (0, robot3_1.immediate)("authRequired", (0, robot3_1.guard)(noToken))),
      authRequired: (0, robot3_1.state)((0, robot3_1.transition)("initiateAuth", "authInProgress"), (0, robot3_1.transition)("send", "authRequired", (0, robot3_1.reduce)(enqueueMessage)), (0, robot3_1.transition)("close", "idle", (0, robot3_1.reduce)(closeConnection))),
      authInProgress: (0, robot3_1.state)((0, robot3_1.transition)("authenticated", "connecting", (0, robot3_1.reduce)(setToken)), (0, robot3_1.transition)("unauthorized", "idle", (0, robot3_1.reduce)(expireToken), (0, robot3_1.reduce)(closeConnection)), (0, robot3_1.transition)("send", "authInProgress", (0, robot3_1.reduce)(enqueueMessage)), (0, robot3_1.transition)("close", "idle", (0, robot3_1.reduce)(closeConnection))),
      active: (0, robot3_1.state)((0, robot3_1.transition)("send", "active", (0, robot3_1.reduce)(sendMessage)), (0, robot3_1.transition)("authenticated", "active", (0, robot3_1.reduce)(setToken)), (0, robot3_1.transition)("unauthorized", "idle", (0, robot3_1.reduce)(expireToken)), (0, robot3_1.transition)("connectionClosed", "idle", (0, robot3_1.reduce)(expireToken), (0, robot3_1.reduce)(closeConnection)), (0, robot3_1.transition)("close", "idle", (0, robot3_1.reduce)(expireToken), (0, robot3_1.reduce)(closeConnection)))
    }, initialState);
    var connectionCache = /* @__PURE__ */ new Map();
    function reuseInterpreter(key, throttleInterval, onChange, callbacks, dispose, handleId) {
      if (!connectionCache.has(key)) {
        const service = (0, robot3_1.interpret)(connectionStateMachine, onChange);
        const guardedSend = (event) => {
          if (connectionCache.get(key) === cached2 && !cached2.disposed) {
            return service.send(event);
          }
        };
        const cached2 = {
          service,
          throttledSend: throttleInterval > 0 ? (0, utils_1.throttle)(guardedSend, throttleInterval, true) : service.send,
          callbacks,
          dispose,
          disposed: false,
          handleId
        };
        connectionCache.set(key, cached2);
      }
      const cached = connectionCache.get(key);
      cached.handleId = handleId;
      cached.callbacks = callbacks;
      cached.disposed = false;
      return cached;
    }
    var noop = () => {
    };
    var NoOpConnection = {
      send: noop,
      close: noop
    };
    function handleRealtimeMessage({ data, decodeMessage, onResult, onError, send, isCurrent }) {
      const handleDecoded = (decoded) => {
        if ((0, protocol_1.isUnauthorizedError)(decoded)) {
          send({
            type: "unauthorized",
            error: new Error("Unauthorized")
          });
          return;
        }
        if ((0, protocol_1.isSuccessfulResult)(decoded)) {
          onResult(decoded);
          return;
        }
        if ((0, protocol_1.isFalErrorResult)(decoded)) {
          if (decoded.error === "TIMEOUT") {
            return;
          }
          onError(new response_1.ApiError({
            message: `${decoded.error}: ${decoded.reason}`,
            // TODO better error status code
            status: 400,
            body: decoded
          }));
          return;
        }
      };
      Promise.resolve(decodeMessage ? decodeMessage(data) : data).then((decoded) => {
        if (isCurrent())
          handleDecoded(decoded);
      }).catch((error) => {
        var _a;
        if (!isCurrent())
          return;
        onError(new response_1.ApiError({
          message: (_a = error === null || error === void 0 ? void 0 : error.message) !== null && _a !== void 0 ? _a : "Failed to decode realtime message",
          status: 400
        }));
      });
    }
    function createRealtimeClient({ config, getClient }) {
      const realtimeClient = {
        connect(app, handler) {
          const {
            // if running on React in the server, set clientOnly to true by default
            clientOnly = (0, utils_1.isReact)() && !(0, runtime_1.isBrowser)(),
            connectionKey = crypto.randomUUID(),
            maxBuffering,
            path,
            throttleInterval = protocol_1.DEFAULT_THROTTLE_INTERVAL,
            encodeMessage: encodeMessageOverride,
            decodeMessage: decodeMessageOverride,
            tokenProvider,
            tokenExpirationSeconds
          } = handler;
          if (clientOnly && !(0, runtime_1.isBrowser)()) {
            return NoOpConnection;
          }
          const tokenScope = (0, protocol_1.realtimeTokenScope)(app, path);
          const encodeMessageFn = encodeMessageOverride !== null && encodeMessageOverride !== void 0 ? encodeMessageOverride : ((input) => (0, protocol_1.encodeRealtimeMessage)(input));
          const decodeMessageFn = decodeMessageOverride !== null && decodeMessageOverride !== void 0 ? decodeMessageOverride : ((data) => (0, protocol_1.decodeRealtimeMessage)(data));
          let previousState;
          let latestEnqueuedMessage;
          let tokenRefreshTimer;
          let tokenRefreshGeneration = 0;
          const callbacks = {
            decodeMessage: decodeMessageFn,
            onError: handler.onError,
            onResult: handler.onResult,
            onClose: handler.onClose
          };
          const handleId = Symbol(connectionKey);
          const dispose = () => {
            tokenRefreshGeneration++;
            clearTimeout(tokenRefreshTimer);
            tokenRefreshTimer = void 0;
          };
          const getCallbacks = () => {
            var _a;
            return (_a = connectionCache.get(connectionKey)) === null || _a === void 0 ? void 0 : _a.callbacks;
          };
          const stateMachine = reuseInterpreter(connectionKey, throttleInterval, ({ context, machine, send: send2 }) => {
            const { enqueuedMessage, token, websocket } = context;
            latestEnqueuedMessage = enqueuedMessage;
            if (machine.current === "active" && // Explicit undefined check: the message is already encoded, and a custom encoder can
            // legitimately produce "" (an empty heartbeat frame) — truthiness would strand it.
            enqueuedMessage !== void 0 && (websocket === null || websocket === void 0 ? void 0 : websocket.readyState) === WebSocket.OPEN) {
              send2({ type: "send", message: enqueuedMessage });
            }
            if (machine.current === "authRequired" && token === void 0 && previousState !== machine.current) {
              send2({ type: "initiateAuth" });
              tokenRefreshGeneration++;
              const generation = tokenRefreshGeneration;
              const scope = tokenScope;
              const fetchToken = tokenProvider ? () => tokenProvider(scope) : () => {
                console.warn("[fal.realtime] Using the default token provider is deprecated. Please provide a `tokenProvider` function to `fal.realtime.connect()`. See https://docs.fal.ai/model-apis/client#client-side-usage-with-token-provider for more information.");
                return (0, auth_1.getTemporaryAuthToken)(app, config);
              };
              const effectiveExpiration = tokenProvider ? tokenExpirationSeconds : auth_1.TOKEN_EXPIRATION_SECONDS;
              const scheduleTokenRefresh = effectiveExpiration !== void 0 ? () => {
                if (stateMachine.disposed)
                  return;
                clearTimeout(tokenRefreshTimer);
                const refreshMs = Math.round(effectiveExpiration * 0.9 * 1e3);
                tokenRefreshTimer = setTimeout(() => {
                  if (stateMachine.disposed || generation !== tokenRefreshGeneration) {
                    return;
                  }
                  fetchToken().then((newToken) => {
                    if (stateMachine.disposed || generation !== tokenRefreshGeneration) {
                      return;
                    }
                    queueMicrotask(() => {
                      if (!stateMachine.disposed) {
                        send2({ type: "authenticated", token: newToken });
                      }
                    });
                    scheduleTokenRefresh();
                  }).catch(() => {
                    if (stateMachine.disposed || generation !== tokenRefreshGeneration) {
                      return;
                    }
                    const retryMs = Math.round(effectiveExpiration * 0.05 * 1e3);
                    tokenRefreshTimer = setTimeout(() => {
                      scheduleTokenRefresh();
                    }, retryMs);
                  });
                }, refreshMs);
              } : noop;
              fetchToken().then((token2) => {
                if (stateMachine.disposed)
                  return;
                queueMicrotask(() => {
                  if (!stateMachine.disposed) {
                    send2({ type: "authenticated", token: token2 });
                  }
                });
                scheduleTokenRefresh();
              }).catch((error) => {
                var _a;
                if (stateMachine.disposed)
                  return;
                const { onError = noop } = (_a = getCallbacks()) !== null && _a !== void 0 ? _a : {};
                const authError = error instanceof response_1.ApiError ? error : new response_1.ApiError({
                  message: error instanceof Error ? error.message : String(error),
                  status: 401,
                  body: error
                });
                queueMicrotask(() => {
                  if (stateMachine.disposed)
                    return;
                  send2({ type: "unauthorized", error });
                  try {
                    onError(authError);
                  } catch (_a2) {
                  }
                });
              });
            }
            if (machine.current === "connecting" && previousState !== machine.current && token !== void 0) {
              const ws = new WebSocket((0, protocol_1.buildRealtimeUrl)(app, { token, maxBuffering, path }));
              ws.onopen = () => {
                var _a, _b;
                if (stateMachine.disposed) {
                  ws.close();
                  return;
                }
                send2({ type: "connected", websocket: ws });
                const queued = (_b = (_a = stateMachine.service.context) === null || _a === void 0 ? void 0 : _a.enqueuedMessage) !== null && _b !== void 0 ? _b : latestEnqueuedMessage;
                if (queued !== void 0) {
                  ws.send(queued);
                  stateMachine.service.context = Object.assign(Object.assign({}, stateMachine.service.context), { enqueuedMessage: void 0 });
                }
              };
              ws.onclose = (event) => {
                var _a, _b, _c;
                if (stateMachine.disposed)
                  return;
                if (event.code !== protocol_1.WebSocketErrorCodes.NORMAL_CLOSURE) {
                  const { onError = noop } = (_a = getCallbacks()) !== null && _a !== void 0 ? _a : {};
                  onError(new response_1.ApiError({
                    message: `Error closing the connection: ${event.reason}`,
                    status: event.code
                  }));
                }
                send2({
                  type: "connectionClosed",
                  code: event.code,
                  reason: event.reason
                });
                if (event.code === protocol_1.WebSocketErrorCodes.NORMAL_CLOSURE) {
                  (_c = (_b = getCallbacks()) === null || _b === void 0 ? void 0 : _b.onClose) === null || _c === void 0 ? void 0 : _c.call(_b, {
                    code: event.code,
                    reason: event.reason
                  });
                }
              };
              ws.onerror = () => {
                var _a;
                if (stateMachine.disposed)
                  return;
                const { onError = noop } = (_a = getCallbacks()) !== null && _a !== void 0 ? _a : {};
                onError(new response_1.ApiError({ message: "Unknown error", status: 500 }));
              };
              ws.onmessage = (event) => {
                const callbacks2 = getCallbacks();
                if (!callbacks2 || stateMachine.disposed)
                  return;
                const { decodeMessage = decodeMessageFn } = callbacks2;
                handleRealtimeMessage({
                  data: event.data,
                  decodeMessage,
                  // Delivered to the callbacks that are current AT DELIVERY, not the ones captured
                  // when the frame arrived: a same-key reuse (a React re-render) during the async
                  // decode swaps in the newest render's closures, and the frame belongs to them —
                  // freezing the arrival-time identity turned every such re-render into silent
                  // frame loss.
                  onResult: (result) => {
                    var _a;
                    (_a = getCallbacks()) === null || _a === void 0 ? void 0 : _a.onResult(result);
                  },
                  onError: (error) => {
                    var _a, _b;
                    ((_b = (_a = getCallbacks()) === null || _a === void 0 ? void 0 : _a.onError) !== null && _b !== void 0 ? _b : noop)(error);
                  },
                  send: send2,
                  isCurrent: () => {
                    const current = connectionCache.get(connectionKey);
                    const activeSocket = stateMachine.service.context.websocket;
                    return current === stateMachine && !stateMachine.disposed && (activeSocket === ws || activeSocket === void 0);
                  }
                });
              };
            }
            if (previousState === "active" && machine.current !== "active") {
              tokenRefreshGeneration++;
              clearTimeout(tokenRefreshTimer);
              tokenRefreshTimer = void 0;
            }
            previousState = machine.current;
          }, callbacks, dispose, handleId);
          let handleClosed = false;
          const send = (input) => {
            if (handleClosed || stateMachine.disposed || stateMachine.handleId !== handleId) {
              return;
            }
            stateMachine.throttledSend({
              type: "send",
              message: encodeMessageFn(input)
            });
          };
          const close = () => {
            if (handleClosed)
              return;
            handleClosed = true;
            if (stateMachine.handleId !== handleId)
              return;
            if (stateMachine.disposed)
              return;
            stateMachine.disposed = true;
            stateMachine.dispose();
            stateMachine.service.send({ type: "close" });
            connectionCache.delete(connectionKey);
          };
          return {
            send,
            close
          };
        },
        open: void 0
      };
      function open(extension, options) {
        var _a, _b;
        const rawOptionEndpointId = typeof options === "object" && options !== null && "endpointId" in options ? options.endpointId : void 0;
        const optionEndpointId = rawOptionEndpointId == null ? void 0 : String(rawOptionEndpointId);
        const endpointId = (_a = optionEndpointId !== null && optionEndpointId !== void 0 ? optionEndpointId : extension.defaultEndpoint) !== null && _a !== void 0 ? _a : "";
        if (!endpointId) {
          throw new Error(`Realtime extension "${extension.id}" requires an endpointId option when opened explicitly.`);
        }
        if (((_b = extension.supports) === null || _b === void 0 ? void 0 : _b.call(extension, endpointId)) === false) {
          throw new Error(`Realtime extension "${extension.id}" does not support "${endpointId}".`);
        }
        const externalSignal = options === null || options === void 0 ? void 0 : options.abortSignal;
        const controller = new AbortController();
        const cleanups = [];
        const lateCleanups = [];
        let lateCleanupDrainPromise;
        const drainLateCleanups = () => {
          if (lateCleanupDrainPromise)
            return lateCleanupDrainPromise;
          const drain = () => __awaiter(this, void 0, void 0, function* () {
            while (lateCleanups.length > 0) {
              const release = lateCleanups.shift();
              try {
                yield release();
              } catch (_a2) {
              }
            }
          });
          lateCleanupDrainPromise = drain().finally(() => {
            lateCleanupDrainPromise = void 0;
            if (lateCleanups.length > 0)
              return drainLateCleanups();
          });
          return lateCleanupDrainPromise;
        };
        let teardownRunning = false;
        let teardownCompleted = false;
        let closed = false;
        let cleanupPromise;
        let session;
        let extensionClose;
        let sessionClosePromise;
        let sessionCloseInProgress = false;
        let state = "opening";
        const onState = options === null || options === void 0 ? void 0 : options.onState;
        const setState = (next) => {
          if (state === next || state === "closed" || state === "failed")
            return;
          state = next;
          try {
            onState === null || onState === void 0 ? void 0 : onState(next);
          } catch (_a2) {
          }
        };
        const closeSession2 = () => {
          if (!extensionClose)
            return Promise.resolve();
          if (!sessionClosePromise) {
            const closeExtension = extensionClose;
            sessionClosePromise = Promise.resolve().then(() => __awaiter(this, void 0, void 0, function* () {
              sessionCloseInProgress = true;
              try {
                yield closeExtension();
              } finally {
                sessionCloseInProgress = false;
              }
            }));
          }
          return sessionClosePromise;
        };
        const cleanup = () => {
          var _a2;
          if (cleanupPromise)
            return cleanupPromise;
          closed = true;
          queuedSends.length = 0;
          cleanupPromise = Promise.resolve().then(() => __awaiter(this, void 0, void 0, function* () {
            teardownRunning = true;
            try {
              yield closeSession2();
            } catch (_a3) {
            } finally {
              for (const release of cleanups.splice(0).reverse()) {
                try {
                  yield release();
                } catch (_b2) {
                }
              }
              teardownCompleted = true;
              yield drainLateCleanups();
              teardownRunning = false;
            }
          }));
          setState("closed");
          controller.abort();
          externalSignal === null || externalSignal === void 0 ? void 0 : externalSignal.removeEventListener("abort", abort);
          if (state !== "failed") {
            rejectReady((_a2 = controller.signal.reason) !== null && _a2 !== void 0 ? _a2 : new Error("Realtime session closed"));
          }
          return cleanupPromise;
        };
        const abort = () => {
          closed = true;
          controller.abort(externalSignal === null || externalSignal === void 0 ? void 0 : externalSignal.reason);
          void cleanup();
        };
        let openTaskPromise;
        let publicClosePromise;
        const publicClose = () => {
          if (!publicClosePromise) {
            const teardown = cleanup();
            publicClosePromise = openTaskPromise ? teardown.then(() => openTaskPromise) : teardown;
          }
          return publicClosePromise;
        };
        const onDiagnostic = options === null || options === void 0 ? void 0 : options.onDiagnostic;
        const diagnostic = (event) => {
          try {
            onDiagnostic === null || onDiagnostic === void 0 ? void 0 : onDiagnostic(event);
          } catch (_a2) {
          }
        };
        const onMedia = options === null || options === void 0 ? void 0 : options.onMedia;
        const media = (stream) => {
          if (closed)
            return;
          try {
            onMedia === null || onMedia === void 0 ? void 0 : onMedia(stream);
          } catch (_a2) {
          }
        };
        const onData = options === null || options === void 0 ? void 0 : options.onData;
        const data = (raw) => {
          if (closed)
            return;
          try {
            onData === null || onData === void 0 ? void 0 : onData(raw);
          } catch (_a2) {
          }
        };
        if (externalSignal === null || externalSignal === void 0 ? void 0 : externalSignal.aborted) {
          controller.abort(externalSignal.reason);
        } else {
          externalSignal === null || externalSignal === void 0 ? void 0 : externalSignal.addEventListener("abort", abort, { once: true });
        }
        const onError = options === null || options === void 0 ? void 0 : options.onError;
        let errorReported = false;
        const reportError = (error) => {
          if (errorReported)
            return;
          errorReported = true;
          try {
            onError === null || onError === void 0 ? void 0 : onError(error);
          } catch (_a2) {
          }
        };
        let resolveReady;
        let rejectReady;
        const ready = new Promise((resolve, reject) => {
          resolveReady = resolve;
          rejectReady = reject;
        });
        ready.catch(() => void 0);
        const MAX_QUEUED_SENDS = 64;
        const queuedSends = [];
        let warnedQueueOverflow = false;
        const queuedSend = (...args) => {
          if (state !== "opening")
            return;
          if (queuedSends.length >= MAX_QUEUED_SENDS) {
            queuedSends.shift();
            if (!warnedQueueOverflow) {
              warnedQueueOverflow = true;
              diagnostic({
                kind: "warning",
                message: `More than ${MAX_QUEUED_SENDS} messages were queued before the session became live; the oldest are being dropped.`
              });
            }
          }
          queuedSends.push(args);
        };
        const flushQueuedSends = () => {
          if (queuedSends.length === 0 || !session)
            return;
          const pending = queuedSends.splice(0);
          let send2;
          try {
            send2 = Reflect.get(session, "send", session);
          } catch (_a2) {
            send2 = void 0;
          }
          if (typeof send2 !== "function") {
            diagnostic({
              kind: "warning",
              message: `The extension session has no send(); ${pending.length} queued message(s) were dropped.`
            });
            return;
          }
          for (const args of pending) {
            if (closed || state === "failed" || state === "closed")
              break;
            try {
              const result = send2.apply(session, args);
              void Promise.resolve(result).catch(() => diagnostic({
                kind: "warning",
                message: "A queued message could not be delivered to the session."
              }));
            } catch (_b2) {
              diagnostic({
                kind: "warning",
                message: "A queued message could not be delivered to the session."
              });
            }
          }
        };
        const activeRequestCombos = /* @__PURE__ */ new Set();
        let sessionComboHookInstalled = false;
        const noopDispose = () => void 0;
        const withSessionSignal = (requestSignal) => {
          if (!requestSignal || requestSignal === controller.signal) {
            return { signal: controller.signal, dispose: noopDispose };
          }
          const combined = new AbortController();
          if (controller.signal.aborted) {
            combined.abort(controller.signal.reason);
            return { signal: combined.signal, dispose: noopDispose };
          }
          if (requestSignal.aborted) {
            combined.abort(requestSignal.reason);
            return { signal: combined.signal, dispose: noopDispose };
          }
          const abortFromRequest = () => {
            activeRequestCombos.delete(entry);
            combined.abort(requestSignal.reason);
          };
          const entry = {
            combined,
            detach: () => requestSignal.removeEventListener("abort", abortFromRequest)
          };
          if (!sessionComboHookInstalled) {
            sessionComboHookInstalled = true;
            controller.signal.addEventListener("abort", () => {
              for (const combo of activeRequestCombos) {
                combo.detach();
                combo.combined.abort(controller.signal.reason);
              }
              activeRequestCombos.clear();
            }, { once: true });
          }
          activeRequestCombos.add(entry);
          requestSignal.addEventListener("abort", abortFromRequest, {
            once: true
          });
          return {
            signal: combined.signal,
            dispose: () => {
              activeRequestCombos.delete(entry);
              entry.detach();
            }
          };
        };
        const disposeWhenBodyConsumed = (response, dispose) => {
          const originalBody = response.body;
          if (!originalBody) {
            dispose();
            return;
          }
          const nativeBodyGetter = (() => {
            let proto = Object.getPrototypeOf(response);
            while (proto) {
              const descriptor = Object.getOwnPropertyDescriptor(proto, "body");
              if (descriptor === null || descriptor === void 0 ? void 0 : descriptor.get)
                return descriptor.get;
              proto = Object.getPrototypeOf(proto);
            }
            return void 0;
          })();
          const currentNativeBody = () => {
            var _a2;
            return (_a2 = nativeBodyGetter === null || nativeBodyGetter === void 0 ? void 0 : nativeBodyGetter.call(response)) !== null && _a2 !== void 0 ? _a2 : originalBody;
          };
          let disposed = false;
          const settle = () => {
            if (!disposed) {
              disposed = true;
              dispose();
            }
          };
          const originalClone = response.clone.bind(response);
          Object.defineProperty(response, "clone", {
            configurable: true,
            writable: true,
            value: () => {
              if (reader || (monitored === null || monitored === void 0 ? void 0 : monitored.locked)) {
                throw new TypeError("Failed to execute 'clone' on 'Response': body is disturbed or locked");
              }
              const cloned = originalClone();
              disposeWhenBodyConsumed(cloned, settle);
              return cloned;
            }
          });
          let monitored;
          let reader;
          let cancelling = false;
          const settleUnlessCancelling = () => {
            if (!cancelling)
              settle();
          };
          const acquireReader = () => {
            if (!reader) {
              reader = currentNativeBody().getReader();
              void reader.closed.then(settleUnlessCancelling, settleUnlessCancelling);
            }
            return reader;
          };
          Object.defineProperty(response, "body", {
            configurable: true,
            enumerable: true,
            get: () => {
              if (!monitored) {
                monitored = new ReadableStream({
                  type: "bytes",
                  pull: (streamController) => __awaiter(this, void 0, void 0, function* () {
                    var _a2;
                    const { done, value } = yield acquireReader().read();
                    if (done) {
                      streamController.close();
                      (_a2 = streamController.byobRequest) === null || _a2 === void 0 ? void 0 : _a2.respond(0);
                      settle();
                      return;
                    }
                    if (value && value.byteLength > 0) {
                      streamController.enqueue(value);
                    }
                  }),
                  cancel: (reason) => __awaiter(this, void 0, void 0, function* () {
                    cancelling = true;
                    try {
                      yield reader ? reader.cancel(reason) : currentNativeBody().cancel(reason);
                    } finally {
                      settle();
                    }
                  })
                }, { highWaterMark: 0 });
              }
              return monitored;
            }
          });
          for (const method of [
            "arrayBuffer",
            "blob",
            "bytes",
            "formData",
            "json",
            "text"
          ]) {
            const original = response[method];
            if (typeof original !== "function")
              continue;
            Object.defineProperty(response, method, {
              configurable: true,
              writable: true,
              value: function patched(...args) {
                if (reader || (monitored === null || monitored === void 0 ? void 0 : monitored.locked)) {
                  return Promise.reject(new TypeError(`Failed to execute '${method}' on 'Response': body is disturbed or locked`));
                }
                return original.apply(this, args).finally(settle);
              }
            });
          }
        };
        const send = (...args) => {
          if (state === "failed" || state === "closed")
            return;
          if (!session) {
            queuedSend(...args);
            return;
          }
          const sessionSend = Reflect.get(session, "send", session);
          if (typeof sessionSend !== "function") {
            diagnostic({
              kind: "warning",
              message: "The extension session has no send(); the message was dropped."
            });
            return;
          }
          const result = sessionSend.apply(session, args);
          if (result && typeof result.then === "function") {
            void Promise.resolve(result).catch(() => diagnostic({
              kind: "warning",
              message: "A message could not be delivered to the session."
            }));
          }
        };
        const handle = {
          get state() {
            return state;
          },
          // The extension's own session: undefined while opening, set once negotiation completes,
          // and left readable after close so late observers see what they held rather than a hole.
          get session() {
            return session;
          },
          ready,
          send,
          close: publicClose
        };
        const openTask = () => __awaiter(this, void 0, void 0, function* () {
          var _a2, _b2, _c;
          try {
            yield Promise.resolve();
            if (controller.signal.aborted) {
              throw (_a2 = controller.signal.reason) !== null && _a2 !== void 0 ? _a2 : new DOMException("Realtime open aborted", "AbortError");
            }
            session = yield extension.open({
              endpointId,
              signal: controller.signal,
              run: (id, runOptions) => {
                if (closed || controller.signal.aborted) {
                  throw new Error("Realtime extension run() was called after the session ended.");
                }
                const normalizedId = id.trim();
                if (/^[a-z][a-z\d+.-]*:/i.test(normalizedId) || normalizedId.startsWith("//")) {
                  throw new Error("Realtime extension run() requires an app endpoint id, not an absolute URL.");
                }
                if (!getClient) {
                  throw new Error("This realtime client was created without fal request access.");
                }
                return getClient().run(normalizedId, runOptions);
              },
              connect: realtimeClient.connect,
              // Credentials, request middleware and proxy come from the parent client, so a proxied
              // application stays proxied and the extension never sees a key. Raw `Response` rather than
              // a parsed result: this reaches infrastructure that does not speak fal's result envelope.
              fetch: (url_1, ...args_1) => __awaiter(this, [url_1, ...args_1], void 0, function* (url, init = {}) {
                var _a3;
                assertFalInfrastructureUrl(url);
                if (init.body !== void 0 && typeof init.body !== "string") {
                  throw new Error("Realtime extension fetch() supports JSON string bodies only.");
                }
                const { fetch: doFetch, credentials: credentialsValue } = config;
                const credentials = typeof credentialsValue === "function" ? credentialsValue() : credentialsValue;
                let requestHeaders;
                if (init.headers !== void 0) {
                  const normalized = {};
                  new Headers(init.headers).forEach((value, key) => {
                    normalized[key] = value;
                  });
                  requestHeaders = normalized;
                }
                const requestedMethod = ((_a3 = init.method) !== null && _a3 !== void 0 ? _a3 : "GET").toUpperCase();
                if (requestedMethod !== "GET" && requestedMethod !== "POST") {
                  throw new Error(`Realtime extension fetch() supports GET and POST only (got ${requestedMethod}).`);
                }
                const { method, url: targetUrl, headers } = yield config.requestMiddleware({
                  method: requestedMethod,
                  url,
                  headers: requestHeaders
                });
                const finalHeaders = new Headers();
                if (credentials) {
                  finalHeaders.set("Authorization", `Key ${credentials}`);
                }
                for (const [name, value] of Object.entries(headers !== null && headers !== void 0 ? headers : {})) {
                  finalHeaders.set(name, Array.isArray(value) ? value.join(", ") : value);
                }
                const { signal, dispose } = withSessionSignal(init.signal);
                try {
                  const response = yield doFetch(targetUrl, Object.assign(Object.assign({}, init), {
                    method,
                    signal,
                    headers: finalHeaders
                  }));
                  if (dispose !== noopDispose) {
                    disposeWhenBodyConsumed(response, dispose);
                  }
                  return response;
                } catch (error) {
                  dispose();
                  throw error;
                }
              }),
              gatherIce: (pc, iceOptions) => __awaiter(this, void 0, void 0, function* () {
                const { signal, dispose } = withSessionSignal(iceOptions === null || iceOptions === void 0 ? void 0 : iceOptions.signal);
                try {
                  return yield (0, ice_1.gatherIceCandidates)(pc, Object.assign(Object.assign({}, iceOptions), { signal, onProgress: (result) => diagnostic({
                    kind: "progress",
                    phase: "ice-gathering",
                    detail: Object.assign({}, result)
                  }) }));
                } finally {
                  dispose();
                }
              }),
              diagnostic,
              media,
              data,
              fail: (message, observed) => __awaiter(this, void 0, void 0, function* () {
                if (closed)
                  return;
                setState("failed");
                diagnostic({ kind: "failure", message, observed });
                const failure = new Error(message);
                reportError(failure);
                rejectReady(failure);
                yield cleanup();
              }),
              addCleanup: (release) => {
                if (closed) {
                  lateCleanups.push(release);
                  if (teardownCompleted)
                    void drainLateCleanups();
                } else {
                  cleanups.push(release);
                }
              },
              // `teardownRunning` in the guard, not `closed`: a cleanup release that awaits
              // context.close() (or the patched session.close) would otherwise receive the
              // memoized teardown promise FROM INSIDE that promise's own body — a circular await
              // that hangs every close() forever. Callers OUTSIDE the body (an abort listener,
              // late app code) still share the real teardown through cleanup()'s memo.
              close: () => sessionCloseInProgress || teardownRunning ? Promise.resolve() : cleanup()
            }, options);
            extensionClose = session.close.bind(session);
            const patchedClose = () => sessionCloseInProgress || teardownRunning ? Promise.resolve() : cleanup();
            const closePatched = Reflect.set(session, "close", patchedClose, session);
            const statePatched = Reflect.defineProperty(session, "state", {
              get: () => state,
              set: () => void 0,
              enumerable: false,
              configurable: true
            });
            const patchWarningPending = !closePatched || !statePatched;
            if (controller.signal.aborted) {
              try {
                yield closeSession2();
              } catch (_d) {
              }
              yield cleanup();
              yield drainLateCleanups();
              throw (_b2 = controller.signal.reason) !== null && _b2 !== void 0 ? _b2 : new Error("Realtime open aborted");
            }
            flushQueuedSends();
            if (patchWarningPending) {
              diagnostic({
                kind: "warning",
                message: "The extension session could not be patched (frozen or sealed); handle.session.close() will bypass managed teardown \u2014 use handle.close()."
              });
            }
            if (controller.signal.aborted || state === "failed" || state === "closed") {
              throw (_c = controller.signal.reason) !== null && _c !== void 0 ? _c : new Error("Realtime session ended while delivering queued sends");
            }
            resolveReady(handle);
            setState("live");
          } catch (error) {
            const wasTerminal = state === "failed" || state === "closed";
            const cancelled = controller.signal.aborted && state !== "failed";
            if (!cancelled) {
              setState("failed");
            }
            if (state === "failed") {
              if (!wasTerminal) {
                diagnostic({
                  kind: "failure",
                  message: error instanceof Error ? error.message : String(error)
                });
              }
              reportError(error);
            }
            rejectReady(error);
            yield cleanup();
            yield drainLateCleanups();
          }
        });
        openTaskPromise = openTask();
        return handle;
      }
      realtimeClient.open = open;
      return realtimeClient;
    }
  }
});

// node_modules/@fal-ai/client/src/client.js
var require_client = __commonJS({
  "node_modules/@fal-ai/client/src/client.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.createFalClient = createFalClient;
    var config_1 = require_config();
    var headers_1 = require_headers();
    var queue_1 = require_queue();
    var realtime_1 = require_realtime();
    var request_1 = require_request();
    var response_1 = require_response();
    var storage_1 = require_storage();
    var streaming_1 = require_streaming();
    function createFalClient(userConfig = {}) {
      const config = (0, config_1.createConfig)(userConfig);
      const storage = (0, storage_1.createStorageClient)({ config });
      const queue = (0, queue_1.createQueueClient)({ config, storage });
      const streaming = (0, streaming_1.createStreamingClient)({ config, storage });
      const realtime = (0, realtime_1.createRealtimeClient)({ config, getClient: () => client });
      const client = {
        queue,
        realtime,
        storage,
        streaming,
        stream: streaming.stream,
        run(endpointId_1) {
          return __awaiter(this, arguments, void 0, function* (endpointId, options = {}) {
            const input = options.input ? yield storage.transformInput(options.input) : void 0;
            return (0, request_1.dispatchRequest)({
              method: options.method,
              targetUrl: (0, request_1.buildUrl)(endpointId, options),
              input,
              // TODO: consider supporting custom headers in fal.run() as well
              headers: Object.assign(Object.assign({}, (0, storage_1.buildObjectLifecycleHeaders)(options.storageSettings)), (0, headers_1.buildTimeoutHeaders)(options.startTimeout)),
              config: Object.assign(Object.assign({}, config), { responseHandler: response_1.resultResponseHandler }),
              options: {
                signal: options.abortSignal,
                retry: {
                  maxRetries: 3,
                  baseDelay: 500,
                  maxDelay: 15e3
                }
              }
            });
          });
        },
        subscribe: (endpointId, options) => __awaiter(this, void 0, void 0, function* () {
          const { request_id: requestId } = yield queue.submit(endpointId, options);
          if (options.onEnqueue) {
            options.onEnqueue(requestId);
          }
          yield queue.subscribeToStatus(endpointId, Object.assign({ requestId }, options));
          return queue.result(endpointId, { requestId });
        })
      };
      return client;
    }
  }
});

// node_modules/@fal-ai/client/src/realtime/extension.js
var require_extension = __commonJS({
  "node_modules/@fal-ai/client/src/realtime/extension.js"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.defineRealtimeExtension = defineRealtimeExtension;
    function defineRealtimeExtension(extension) {
      return extension;
    }
  }
});

// node_modules/@fal-ai/client/src/types/common.js
var require_common = __commonJS({
  "node_modules/@fal-ai/client/src/types/common.js"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.isQueueStatus = isQueueStatus;
    exports.isCompletedQueueStatus = isCompletedQueueStatus;
    function isQueueStatus(obj) {
      return obj && obj.status && obj.response_url;
    }
    function isCompletedQueueStatus(obj) {
      return isQueueStatus(obj) && obj.status === "COMPLETED";
    }
  }
});

// node_modules/@fal-ai/client/src/index.js
var require_src = __commonJS({
  "node_modules/@fal-ai/client/src/index.js"(exports) {
    "use strict";
    var __createBinding = exports && exports.__createBinding || (Object.create ? (function(o, m, k, k2) {
      if (k2 === void 0) k2 = k;
      var desc = Object.getOwnPropertyDescriptor(m, k);
      if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
        desc = { enumerable: true, get: function() {
          return m[k];
        } };
      }
      Object.defineProperty(o, k2, desc);
    }) : (function(o, m, k, k2) {
      if (k2 === void 0) k2 = k;
      o[k2] = m[k];
    }));
    var __exportStar = exports && exports.__exportStar || function(m, exports2) {
      for (var p in m) if (p !== "default" && !Object.prototype.hasOwnProperty.call(exports2, p)) __createBinding(exports2, m, p);
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.fal = exports.parseEndpointId = exports.isRetryableError = exports.ValidationError = exports.ApiError = exports.defineRealtimeExtension = exports.withProxy = exports.withMiddleware = exports.createFalClient = void 0;
    var client_1 = require_client();
    var client_2 = require_client();
    Object.defineProperty(exports, "createFalClient", { enumerable: true, get: function() {
      return client_2.createFalClient;
    } });
    var middleware_1 = require_middleware();
    Object.defineProperty(exports, "withMiddleware", { enumerable: true, get: function() {
      return middleware_1.withMiddleware;
    } });
    Object.defineProperty(exports, "withProxy", { enumerable: true, get: function() {
      return middleware_1.withProxy;
    } });
    var extension_1 = require_extension();
    Object.defineProperty(exports, "defineRealtimeExtension", { enumerable: true, get: function() {
      return extension_1.defineRealtimeExtension;
    } });
    var response_1 = require_response();
    Object.defineProperty(exports, "ApiError", { enumerable: true, get: function() {
      return response_1.ApiError;
    } });
    Object.defineProperty(exports, "ValidationError", { enumerable: true, get: function() {
      return response_1.ValidationError;
    } });
    var retry_1 = require_retry();
    Object.defineProperty(exports, "isRetryableError", { enumerable: true, get: function() {
      return retry_1.isRetryableError;
    } });
    __exportStar(require_common(), exports);
    var utils_1 = require_utils();
    Object.defineProperty(exports, "parseEndpointId", { enumerable: true, get: function() {
      return utils_1.parseEndpointId;
    } });
    exports.fal = (function createSingletonFalClient() {
      let currentInstance = (0, client_1.createFalClient)();
      return {
        config(config) {
          currentInstance = (0, client_1.createFalClient)(config);
        },
        get queue() {
          return currentInstance.queue;
        },
        get realtime() {
          return currentInstance.realtime;
        },
        get storage() {
          return currentInstance.storage;
        },
        get streaming() {
          return currentInstance.streaming;
        },
        run(id, options) {
          return currentInstance.run(id, options);
        },
        subscribe(endpointId, options) {
          return currentInstance.subscribe(endpointId, options);
        },
        stream(endpointId, options) {
          return currentInstance.stream(endpointId, options);
        }
      };
    })();
  }
});

// node_modules/@fal-ai/client/src/realtime/abort.js
var require_abort = __commonJS({
  "node_modules/@fal-ai/client/src/realtime/abort.js"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.throwIfRealtimeAborted = throwIfRealtimeAborted;
    function throwIfRealtimeAborted(signal) {
      var _a;
      if (!signal.aborted)
        return;
      throw (_a = signal.reason) !== null && _a !== void 0 ? _a : new DOMException("Realtime operation aborted", "AbortError");
    }
  }
});

// node_modules/@fal-ai/client/src/realtime/wma-media.js
var require_wma_media = __commonJS({
  "node_modules/@fal-ai/client/src/realtime/wma-media.js"(exports) {
    "use strict";
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.normalizeWmaReceiveTrack = normalizeWmaReceiveTrack;
    exports.applyWmaCodecPreferences = applyWmaCodecPreferences;
    exports.applyWmaOpusPreferences = applyWmaOpusPreferences;
    function normalizeWmaReceiveTrack(track) {
      const value = typeof track === "string" ? { kind: track } : track;
      if (!value || value.kind !== "audio" && value.kind !== "video") {
        throw new TypeError("WMA receive kind must be audio or video.");
      }
      const codecs = value.codecPreferences;
      if (codecs !== void 0 && (!Array.isArray(codecs) || codecs.some((codec) => typeof codec !== "string" || !new RegExp(`^${value.kind}/[a-z0-9.+_-]+$`, "i").test(codec)))) {
        throw new TypeError("WMA codecPreferences must contain MIME types matching the track kind.");
      }
      const opus = value.opus;
      if (opus !== void 0) {
        if (value.kind !== "audio" || !opus || typeof opus !== "object" || Array.isArray(opus)) {
          throw new TypeError("WMA Opus preferences require an audio receive track.");
        }
        if (opus.stereo !== void 0 && typeof opus.stereo !== "boolean") {
          throw new TypeError("WMA Opus stereo must be a boolean.");
        }
        const bitrate = opus.maxAverageBitrate;
        if (bitrate !== void 0 && (!Number.isInteger(bitrate) || bitrate < 6e3 || bitrate > 51e4)) {
          throw new TypeError("WMA Opus maxAverageBitrate must be an integer from 6000 to 510000 bits/s.");
        }
      }
      const common = Object.assign({}, codecs !== void 0 ? { codecPreferences: codecs.map((codec) => codec.toLowerCase()) } : {});
      return value.kind === "audio" ? Object.assign(Object.assign(Object.assign({}, common), { kind: "audio" }), opus !== void 0 ? { opus: Object.assign({}, opus) } : {}) : Object.assign(Object.assign({}, common), { kind: "video" });
    }
    function applyWmaCodecPreferences(transceiver, track, warn) {
      var _a, _b;
      const preferred = track.codecPreferences;
      if (!(preferred === null || preferred === void 0 ? void 0 : preferred.length))
        return;
      if (typeof transceiver.setCodecPreferences !== "function" || typeof RTCRtpReceiver === "undefined" || typeof RTCRtpReceiver.getCapabilities !== "function") {
        throw new Error("WMA codecPreferences are not supported by this browser.");
      }
      const codecs = (_b = (_a = RTCRtpReceiver.getCapabilities(track.kind)) === null || _a === void 0 ? void 0 : _a.codecs) !== null && _b !== void 0 ? _b : [];
      for (const mime of preferred) {
        if (!codecs.some((codec) => codec.mimeType.toLowerCase() === mime)) {
          warn(`WMA receive codec ${mime} is unavailable; retaining browser fallbacks.`);
        }
      }
      if (!codecs.some((codec) => preferred.includes(codec.mimeType.toLowerCase())))
        return;
      const rank = (mime) => {
        const index = preferred.indexOf(mime.toLowerCase());
        return index === -1 ? preferred.length : index;
      };
      transceiver.setCodecPreferences([...codecs].sort((a, b) => rank(a.mimeType) - rank(b.mimeType)));
    }
    function applyWmaOpusPreferences(sdp, tracks) {
      if (!tracks.some((track) => {
        var _a, _b;
        return ((_a = track.opus) === null || _a === void 0 ? void 0 : _a.stereo) !== void 0 || ((_b = track.opus) === null || _b === void 0 ? void 0 : _b.maxAverageBitrate) !== void 0;
      }))
        return sdp;
      const sections = sdp.split(/(?=^m=)/m);
      const offset = sections[0].startsWith("m=") ? 0 : 1;
      tracks.forEach((track, index) => {
        const options = track.opus;
        if (!options || options.stereo === void 0 && options.maxAverageBitrate === void 0)
          return;
        const section = sections[offset + index];
        if (!(section === null || section === void 0 ? void 0 : section.startsWith("m=audio ")))
          throw new Error("WMA Opus receive section is missing.");
        const newline = section.includes("\r\n") ? "\r\n" : "\n";
        const lines = section.split(newline);
        const payloads = lines.flatMap((line) => {
          const match = /^a=rtpmap:(\d+) opus\/48000\/2\s*$/i.exec(line);
          return match ? [match[1]] : [];
        });
        if (!payloads.length)
          throw new Error("WMA Opus preferences require an offered Opus codec.");
        const parameters = {};
        if (options.stereo !== void 0)
          parameters.stereo = options.stereo ? "1" : "0";
        if (options.maxAverageBitrate !== void 0)
          parameters.maxaveragebitrate = String(options.maxAverageBitrate);
        for (const payload of payloads) {
          const prefix = `a=fmtp:${payload} `;
          const fmtpIndex = lines.findIndex((line) => line.startsWith(prefix));
          const previous = fmtpIndex === -1 ? [] : lines[fmtpIndex].slice(prefix.length).split(";");
          const retained = previous.filter((parameter) => !Object.prototype.hasOwnProperty.call(parameters, parameter.split("=")[0].trim().toLowerCase()));
          const fmtp = prefix + [
            ...retained,
            ...Object.entries(parameters).map(([key, value]) => `${key}=${value}`)
          ].join(";");
          if (fmtpIndex !== -1)
            lines[fmtpIndex] = fmtp;
          else {
            const rtpIndex = lines.findIndex((line) => line.toLowerCase().startsWith(`a=rtpmap:${payload} `));
            lines.splice(rtpIndex + 1, 0, fmtp);
          }
        }
        sections[offset + index] = lines.join(newline);
      });
      return sections.join("");
    }
  }
});

// node_modules/@fal-ai/client/src/realtime/wma.js
var require_wma = __commonJS({
  "node_modules/@fal-ai/client/src/realtime/wma.js"(exports) {
    "use strict";
    var __awaiter = exports && exports.__awaiter || function(thisArg, _arguments, P, generator) {
      function adopt(value) {
        return value instanceof P ? value : new P(function(resolve) {
          resolve(value);
        });
      }
      return new (P || (P = Promise))(function(resolve, reject) {
        function fulfilled(value) {
          try {
            step(generator.next(value));
          } catch (e) {
            reject(e);
          }
        }
        function rejected(value) {
          try {
            step(generator["throw"](value));
          } catch (e) {
            reject(e);
          }
        }
        function step(result) {
          result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
        }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
      });
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.wma = wma2;
    var abort_1 = require_abort();
    var extension_1 = require_extension();
    var ice_1 = require_ice();
    var wma_media_1 = require_wma_media();
    var WMA_URL = "https://wma.fal.run";
    var ICE_DISCOVERY_TIMEOUT_MS = 5e3;
    var HEARTBEAT_INTERVAL_MS = 5e3;
    var HEARTBEAT_TIMEOUT_MS = 4e3;
    var NETWORK_INFO_REQUEST_TYPE = "wma.network-info.request";
    var NETWORK_INFO_RESPONSE_TYPE = "wma.network-info.response";
    var NETWORK_INFO_TIMEOUT_MS = 1e4;
    var BROWSER_NETWORK_INFO_TIMEOUT_MS = 5e3;
    var BROWSER_NETWORK_INFO_POLL_MS = 100;
    var MAX_QUEUED_MESSAGES = 64;
    var DEFAULT_STUN_URL = "stun:stun.l.google.com:19302";
    function fetchIceServers(context) {
      return __awaiter(this, void 0, void 0, function* () {
        var _a, _b, _c, _d, _e, _f;
        const controller = new AbortController();
        const abortDiscovery = () => controller.abort(context.signal.reason);
        if (context.signal.aborted) {
          abortDiscovery();
        } else {
          context.signal.addEventListener("abort", abortDiscovery, { once: true });
        }
        const discoveryTimeout = setTimeout(() => controller.abort(), ICE_DISCOVERY_TIMEOUT_MS);
        try {
          const response = yield context.fetch(`${WMA_URL}/ice`, {
            method: "POST",
            signal: controller.signal,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ app_id: context.endpointId })
          });
          if (!response.ok) {
            yield response.arrayBuffer().catch(() => void 0);
            throw new Error(`bridge /ice request failed (HTTP ${response.status})`);
          }
          const payload = yield response.json();
          if (Array.isArray(payload.ice_servers) && payload.ice_servers.length > 0) {
            context.diagnostic({
              kind: "progress",
              phase: "ice-servers",
              detail: {
                source: "bridge",
                status: (_a = payload.status) !== null && _a !== void 0 ? _a : "unknown",
                credentialAgeSeconds: (_b = payload.credential_age_seconds) !== null && _b !== void 0 ? _b : 0
              }
            });
            return payload.ice_servers;
          }
          if (payload.status === "app_managed") {
            context.diagnostic({
              kind: "progress",
              phase: "ice-servers",
              detail: { source: "app-managed; trying app fallback" }
            });
          } else {
            throw new Error("bridge /ice response contained no ICE servers");
          }
        } catch (_g) {
          if (context.signal.aborted) {
            throw (_c = context.signal.reason) !== null && _c !== void 0 ? _c : new DOMException("WMA ICE discovery aborted", "AbortError");
          }
          context.diagnostic({
            kind: "progress",
            phase: "ice-servers",
            detail: { source: "bridge-unavailable; trying app fallback" }
          });
        } finally {
          clearTimeout(discoveryTimeout);
          context.signal.removeEventListener("abort", abortDiscovery);
        }
        const fallbackController = new AbortController();
        const abortFallback = () => fallbackController.abort(context.signal.reason);
        if (context.signal.aborted) {
          abortFallback();
        } else {
          context.signal.addEventListener("abort", abortFallback, { once: true });
        }
        const fallbackTimeout = setTimeout(() => fallbackController.abort(), ICE_DISCOVERY_TIMEOUT_MS);
        try {
          const result = yield context.run(`${context.endpointId}/ice`, {
            input: {},
            abortSignal: fallbackController.signal
          });
          const payload = result.data;
          if (Array.isArray(payload === null || payload === void 0 ? void 0 : payload.ice_servers) && payload.ice_servers.length > 0) {
            context.diagnostic({
              kind: "progress",
              phase: "ice-servers",
              detail: {
                source: "app-fallback",
                status: (_d = payload.status) !== null && _d !== void 0 ? _d : "unknown",
                credentialAgeSeconds: (_e = payload.credential_age_seconds) !== null && _e !== void 0 ? _e : 0
              }
            });
            return payload.ice_servers;
          }
          context.diagnostic({
            kind: "progress",
            phase: "ice-servers",
            detail: { source: "empty-ice-response" }
          });
        } catch (exc) {
          if (context.signal.aborted) {
            throw (_f = context.signal.reason) !== null && _f !== void 0 ? _f : new DOMException("WMA ICE discovery aborted", "AbortError");
          }
          console.warn("[wma] /ice unavailable, falling back to STUN:", exc);
          context.diagnostic({
            kind: "progress",
            phase: "ice-servers",
            detail: {
              source: `ice-endpoint-failed: ${exc instanceof Error ? exc.message : String(exc)}`
            }
          });
        } finally {
          clearTimeout(fallbackTimeout);
          context.signal.removeEventListener("abort", abortFallback);
        }
        return [{ urls: DEFAULT_STUN_URL }];
      });
    }
    function readErrorMessage(response) {
      return __awaiter(this, void 0, void 0, function* () {
        var _a;
        const fallback = `WMA session request failed (HTTP ${response.status})`;
        try {
          const data = yield response.json();
          if (typeof data === "object" && data !== null) {
            const record = data;
            for (const field of ["error", "message", "detail"]) {
              const value = record[field];
              if (typeof value === "string" && value)
                return value;
              if (Array.isArray(value) && typeof ((_a = value[0]) === null || _a === void 0 ? void 0 : _a.msg) === "string") {
                return value[0].msg;
              }
            }
          }
        } catch (_b) {
        }
        return fallback;
      });
    }
    function candidateInfo(candidate) {
      var _a, _b, _c, _d, _e, _f;
      const address = String((_b = (_a = candidate.address) !== null && _a !== void 0 ? _a : candidate.ip) !== null && _b !== void 0 ? _b : "unknown");
      const port = Number((_c = candidate.port) !== null && _c !== void 0 ? _c : 0);
      return {
        type: String((_e = (_d = candidate.candidateType) !== null && _d !== void 0 ? _d : candidate.type) !== null && _e !== void 0 ? _e : "unknown"),
        protocol: String((_f = candidate.protocol) !== null && _f !== void 0 ? _f : "unknown").toLowerCase(),
        endpoint: address.includes(":") ? `[${address}]:${port}` : `${address}:${port}`,
        address,
        port,
        relayProtocol: candidate.relayProtocol,
        tcpType: candidate.tcpType,
        relatedAddress: candidate.relatedAddress,
        relatedPort: candidate.relatedPort
      };
    }
    function raceProbeStep(operation, signal, timeoutMs) {
      (0, abort_1.throwIfRealtimeAborted)(signal);
      return new Promise((resolve, reject) => {
        let settled = false;
        const finish = (callback) => {
          if (settled)
            return;
          settled = true;
          clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          callback();
        };
        const onAbort = () => finish(() => reject(signal.reason));
        signal.addEventListener("abort", onAbort, { once: true });
        const timeout = setTimeout(() => finish(() => resolve({ timedOut: true })), timeoutMs);
        operation.then((value) => finish(() => resolve({ timedOut: false, value })), (error) => finish(() => reject(error)));
        if (signal.aborted)
          onAbort();
      });
    }
    function probeDelay(ms, signal) {
      (0, abort_1.throwIfRealtimeAborted)(signal);
      return new Promise((resolve, reject) => {
        let settled = false;
        const finish = (callback) => {
          if (settled)
            return;
          settled = true;
          clearTimeout(timeout);
          signal.removeEventListener("abort", onAbort);
          callback();
        };
        const onAbort = () => finish(() => reject(signal.reason));
        signal.addEventListener("abort", onAbort, { once: true });
        const timeout = setTimeout(() => finish(resolve), ms);
        if (signal.aborted)
          onAbort();
      });
    }
    function browserNetworkPath(pc, sessionId, runnerPath, signal) {
      return __awaiter(this, void 0, void 0, function* () {
        var _a, _b;
        const deadline = Date.now() + BROWSER_NETWORK_INFO_TIMEOUT_MS;
        while (Date.now() < deadline) {
          const statsResult = yield raceProbeStep(pc.getStats(), signal, Math.max(0, deadline - Date.now()));
          if (statsResult.timedOut === true)
            break;
          const report = statsResult.value;
          const stats = /* @__PURE__ */ new Map();
          report.forEach((item) => stats.set(item.id, item));
          const sctp = pc.sctp;
          const dtls = sctp === null || sctp === void 0 ? void 0 : sctp.transport;
          const ice = dtls === null || dtls === void 0 ? void 0 : dtls.iceTransport;
          const selected = ice && typeof ice.getSelectedCandidatePair === "function" ? ice.getSelectedCandidatePair() : void 0;
          let localCandidate;
          let remoteCandidate;
          let pairSelection;
          if (selected) {
            const local = selected.local || selected.localCandidate;
            const remote = selected.remote || selected.remoteCandidate;
            if (local && remote) {
              localCandidate = candidateInfo(local);
              remoteCandidate = candidateInfo(remote);
              pairSelection = "browser-sctp-ice-transport";
            }
          }
          const runnerRemoteEndpoint = (_a = runnerPath === null || runnerPath === void 0 ? void 0 : runnerPath.remoteCandidate) === null || _a === void 0 ? void 0 : _a.endpoint;
          const runnerLocalEndpoint = (_b = runnerPath === null || runnerPath === void 0 ? void 0 : runnerPath.localCandidate) === null || _b === void 0 ? void 0 : _b.endpoint;
          let pair;
          let transport;
          if (!localCandidate && runnerRemoteEndpoint && runnerLocalEndpoint) {
            for (const item of stats.values()) {
              if (item.type !== "candidate-pair" || item.state !== "succeeded")
                continue;
              const local = stats.get(item.localCandidateId);
              const remote = stats.get(item.remoteCandidateId);
              if (local && remote && candidateInfo(local).endpoint === runnerRemoteEndpoint && candidateInfo(remote).endpoint === runnerLocalEndpoint) {
                pair = item;
                pairSelection = "cross-peer-endpoint-match";
                localCandidate = candidateInfo(local);
                remoteCandidate = candidateInfo(remote);
                for (const maybeTransport of stats.values()) {
                  if (maybeTransport.type === "transport" && maybeTransport.selectedCandidatePairId === item.id) {
                    transport = maybeTransport;
                    break;
                  }
                }
                break;
              }
            }
          }
          if (localCandidate && remoteCandidate && !pair) {
            for (const item of stats.values()) {
              if (item.type !== "candidate-pair" || item.state !== "succeeded")
                continue;
              const local = stats.get(item.localCandidateId);
              const remote = stats.get(item.remoteCandidateId);
              if (local && remote && candidateInfo(local).endpoint === localCandidate.endpoint && candidateInfo(remote).endpoint === remoteCandidate.endpoint) {
                pair = item;
                break;
              }
            }
          }
          if (localCandidate && remoteCandidate) {
            return {
              side: "browser",
              sessionId,
              observedAtMs: Date.now(),
              available: true,
              connectionState: pc.connectionState,
              iceConnectionState: pc.iceConnectionState,
              iceRole: (ice === null || ice === void 0 ? void 0 : ice.role) || (transport === null || transport === void 0 ? void 0 : transport.iceRole),
              dtlsState: (dtls === null || dtls === void 0 ? void 0 : dtls.state) || (transport === null || transport === void 0 ? void 0 : transport.dtlsState),
              pairSelection,
              localCandidate,
              remoteCandidate,
              usesTurn: localCandidate.type === "relay" || remoteCandidate.type === "relay",
              browserUsesTurn: localCandidate.type === "relay",
              runnerUsesTurn: remoteCandidate.type === "relay",
              currentRoundTripTimeMs: pair && typeof pair.currentRoundTripTime === "number" ? pair.currentRoundTripTime * 1e3 : void 0,
              availableOutgoingBitrate: pair === null || pair === void 0 ? void 0 : pair.availableOutgoingBitrate
            };
          }
          const remaining = deadline - Date.now();
          if (remaining <= 0)
            break;
          yield probeDelay(Math.min(BROWSER_NETWORK_INFO_POLL_MS, remaining), signal);
        }
        return {
          side: "browser",
          sessionId,
          observedAtMs: Date.now(),
          available: false,
          reason: "browser did not expose the selected SCTP ICE pair",
          connectionState: pc.connectionState,
          iceConnectionState: pc.iceConnectionState
        };
      });
    }
    function normalizeRunnerPath(path) {
      const candidate = (value) => value ? {
        type: value.type,
        protocol: value.protocol,
        endpoint: value.endpoint,
        address: value.address,
        port: value.port,
        relayProtocol: value.relay_protocol,
        tcpType: value.tcp_type,
        relatedAddress: value.related_address,
        relatedPort: value.related_port
      } : void 0;
      return {
        side: "runner",
        sessionId: path.session_id,
        observedAtMs: path.observed_at_ms,
        available: path.available,
        reason: path.reason,
        connectionState: path.connection_state,
        iceConnectionState: path.ice_connection_state,
        iceRole: path.ice_role,
        dtlsState: path.dtls_state,
        pairSelection: "runner-sctp-nominated-pair",
        localCandidate: candidate(path.local_candidate),
        remoteCandidate: candidate(path.remote_candidate),
        usesTurn: path.uses_turn,
        runnerUsesTurn: path.runner_uses_turn,
        browserUsesTurn: path.browser_uses_turn
      };
    }
    function wma2(endpointId) {
      return (0, extension_1.defineRealtimeExtension)({
        id: "fal/wma",
        defaultEndpoint: endpointId,
        open(context, options) {
          return __awaiter(this, void 0, void 0, function* () {
            var _a, _b, _c, _d, _e, _f;
            if (options.negotiationTimeoutMs != null && (!Number.isFinite(options.negotiationTimeoutMs) || options.negotiationTimeoutMs <= 0)) {
              throw new Error("WMA negotiationTimeoutMs must be a positive, finite number.");
            }
            if (options.direction === "stopped") {
              throw new Error('WMA direction cannot be "stopped".');
            }
            if (options.receive !== void 0 && options.direction !== void 0) {
              throw new Error("WMA receive tracks cannot be combined with an explicit direction.");
            }
            const receive = (_a = options.receive) === null || _a === void 0 ? void 0 : _a.map(wma_media_1.normalizeWmaReceiveTrack);
            const iceServers = (_b = options.iceServers) !== null && _b !== void 0 ? _b : yield fetchIceServers(context);
            const pc = new RTCPeerConnection({
              iceServers,
              iceTransportPolicy: options.iceTransportPolicy
            });
            let peerClosed = false;
            const closePeer = () => {
              if (peerClosed)
                return;
              peerClosed = true;
              pc.close();
            };
            context.addCleanup(closePeer);
            const localTracks = (_d = (_c = options.localStream) === null || _c === void 0 ? void 0 : _c.getTracks()) !== null && _d !== void 0 ? _d : [];
            if (receive !== void 0) {
              const unmatchedLocalTracks = [...localTracks];
              for (const preferences of receive) {
                const { kind } = preferences;
                const localIndex = unmatchedLocalTracks.findIndex((track) => track.kind === kind);
                const transceiver = localIndex === -1 ? pc.addTransceiver(kind, { direction: "recvonly" }) : pc.addTransceiver(unmatchedLocalTracks.splice(localIndex, 1)[0], {
                  direction: "sendrecv",
                  streams: [options.localStream]
                });
                (0, wma_media_1.applyWmaCodecPreferences)(transceiver, preferences, (message) => context.diagnostic({ kind: "warning", message }));
              }
              for (const track of unmatchedLocalTracks) {
                pc.addTransceiver(track, {
                  direction: "sendonly",
                  streams: [options.localStream]
                });
              }
            } else if (localTracks.length > 0) {
              for (const track of localTracks) {
                pc.addTransceiver(track, {
                  direction: (_e = options.direction) !== null && _e !== void 0 ? _e : "sendrecv",
                  streams: [options.localStream]
                });
              }
            } else {
              pc.addTransceiver("video", {
                direction: (_f = options.direction) !== null && _f !== void 0 ? _f : "recvonly"
              });
            }
            const observed = {
              host: 0,
              srflx: 0,
              relay: 0,
              errors: /* @__PURE__ */ new Set()
            };
            pc.addEventListener("icecandidateerror", (event) => {
              var _a2, _b2;
              const error = event;
              observed.errors.add(`${(_a2 = error.url) !== null && _a2 !== void 0 ? _a2 : "unknown server"} \u2192 ${error.errorCode} ${(_b2 = error.errorText) !== null && _b2 !== void 0 ? _b2 : ""}`.trim());
            });
            const channel = pc.createDataChannel("control");
            const controlFrameDecoder = new TextDecoder();
            const networkRequests = /* @__PURE__ */ new Map();
            const deliverControlFrame = (raw) => {
              try {
                const message = JSON.parse(raw);
                if ((message === null || message === void 0 ? void 0 : message.type) === NETWORK_INFO_RESPONSE_TYPE) {
                  if (typeof message.request_id !== "string") {
                    context.diagnostic({
                      kind: "warning",
                      message: "A malformed reserved network-info frame was dropped."
                    });
                    return;
                  }
                  const request = networkRequests.get(message.request_id);
                  if (request) {
                    networkRequests.delete(message.request_id);
                    try {
                      request.resolve(normalizeRunnerPath(message.path));
                    } catch (error) {
                      request.reject(error instanceof Error ? error : new Error("WMA runner returned invalid network info"));
                    }
                  }
                  return;
                }
              } catch (_a2) {
              }
              context.data(raw);
            };
            channel.onmessage = (event) => {
              const payload = event.data;
              if (typeof payload === "string") {
                deliverControlFrame(payload);
                return;
              }
              if (payload instanceof ArrayBuffer || ArrayBuffer.isView(payload)) {
                const bytes = payload instanceof ArrayBuffer ? new Uint8Array(payload) : payload;
                deliverControlFrame(controlFrameDecoder.decode(bytes));
                return;
              }
              if (typeof Blob !== "undefined" && payload instanceof Blob && typeof payload.text === "function") {
                void payload.text().then((text) => deliverControlFrame(text), () => context.diagnostic({
                  kind: "warning",
                  message: "A binary control-channel frame could not be decoded and was dropped."
                }));
                return;
              }
              context.diagnostic({
                kind: "warning",
                message: "A control-channel frame with an unsupported payload type was dropped."
              });
            };
            const publishedStreams = /* @__PURE__ */ new WeakSet();
            pc.ontrack = (event) => {
              const streams = event.streams.length > 0 ? event.streams : [new MediaStream([event.track])];
              for (const stream of streams) {
                if (!publishedStreams.has(stream)) {
                  publishedStreams.add(stream);
                  context.media(stream);
                }
              }
            };
            pc.onconnectionstatechange = () => {
              if (pc.connectionState === "failed") {
                const turnOffered = (0, ice_1.countTurnServers)(iceServers);
                const parts = [
                  `ICE could not establish a path (iceConnectionState=${pc.iceConnectionState}).`,
                  `Gathered host ${observed.host}, srflx ${observed.srflx}, relay ${observed.relay} from ${turnOffered} TURN server${turnOffered === 1 ? "" : "s"} offered.`
                ];
                parts.push(observed.errors.size > 0 ? `Servers that errored: ${[...observed.errors].join("; ")}.` : "No ICE server reported an error.");
                if (turnOffered > 0 && observed.relay === 0) {
                  parts.push("TURN was configured and no relay candidate was allocated, so a relayed path was never available to try.");
                }
                void context.fail(parts.join(" "), Object.assign(Object.assign({}, observed), { turnOffered, errors: [...observed.errors].join("; ") }));
                return;
              }
              context.diagnostic({
                kind: "progress",
                phase: "connection-state",
                detail: { state: pc.connectionState }
              });
            };
            const pending = [];
            let resolveControlChannelOpen;
            let rejectControlChannelOpen;
            const controlChannelOpen = new Promise((resolve, reject) => {
              resolveControlChannelOpen = resolve;
              rejectControlChannelOpen = reject;
            });
            void controlChannelOpen.catch(() => void 0);
            let heartbeat = null;
            let heartbeatController = null;
            let heartbeatInFlight = false;
            const networkProbeController = new AbortController();
            let closed = false;
            const teardown = () => {
              if (closed)
                return;
              closed = true;
              networkProbeController.abort(new Error("WMA session closed before the network probe completed"));
              rejectControlChannelOpen(new Error("WMA control channel closed before it opened"));
              for (const [id, request] of [...networkRequests]) {
                networkRequests.delete(id);
                request.reject(new Error("WMA session closed before the network probe completed"));
              }
              pending.length = 0;
              if (heartbeat !== null)
                clearInterval(heartbeat);
              heartbeatController === null || heartbeatController === void 0 ? void 0 : heartbeatController.abort();
              heartbeatController = null;
              channel.close();
              closePeer();
            };
            context.addCleanup(teardown);
            const channelDied = () => {
              if (closed)
                return;
              rejectControlChannelOpen(new Error("WMA control channel closed before it opened"));
              void context.fail("control data channel closed or errored \u2014 SCTP died while ICE may still say connected");
            };
            channel.onclose = channelDied;
            channel.onerror = channelDied;
            const sendPayload = (payload) => {
              if (channel.readyState === "open") {
                channel.send(payload);
              } else if (channel.readyState === "connecting") {
                if (pending.length >= MAX_QUEUED_MESSAGES)
                  pending.shift();
                pending.push(payload);
              }
            };
            channel.onopen = () => {
              resolveControlChannelOpen();
              const queued = pending.splice(0);
              for (let i = 0; i < queued.length; i++) {
                try {
                  channel.send(queued[i]);
                } catch (_a2) {
                  context.diagnostic({
                    kind: "warning",
                    message: `The control channel died while flushing; ${queued.length - i} queued message(s) were dropped.`
                  });
                  break;
                }
              }
            };
            try {
              const offer = yield pc.createOffer();
              if (offer.sdp !== void 0 && receive !== void 0) {
                offer.sdp = (0, wma_media_1.applyWmaOpusPreferences)(offer.sdp, receive);
              }
              const gathering = context.gatherIce(pc, {
                iceServers,
                iceTransportPolicy: options.iceTransportPolicy
              });
              const [gathered_ice] = yield Promise.all([
                gathering,
                pc.setLocalDescription(offer)
              ]);
              observed.host = gathered_ice.host;
              observed.srflx = gathered_ice.srflx;
              observed.relay = gathered_ice.relay;
              if (options.iceTransportPolicy === "relay" && gathered_ice.relay === 0) {
                throw new Error("WMA requires a TURN relay, but ICE gathering produced no relay candidate");
              }
              const gathered = pc.localDescription;
              if (!gathered)
                throw new Error("failed to create WebRTC offer");
              (0, abort_1.throwIfRealtimeAborted)(context.signal);
              const sessionController = new AbortController();
              const abortSession = () => sessionController.abort(context.signal.reason);
              if (context.signal.aborted) {
                abortSession();
              } else {
                context.signal.addEventListener("abort", abortSession, {
                  once: true
                });
              }
              const sessionTimeout = options.negotiationTimeoutMs == null ? void 0 : setTimeout(() => sessionController.abort(), options.negotiationTimeoutMs);
              let answer;
              try {
                const response = yield context.fetch(`${WMA_URL}/session`, {
                  method: "POST",
                  signal: sessionController.signal,
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    app_id: context.endpointId,
                    sdp: gathered.sdp,
                    type: gathered.type
                  })
                });
                if (!response.ok)
                  throw new Error(yield readErrorMessage(response));
                answer = yield response.json();
              } finally {
                if (sessionTimeout !== void 0)
                  clearTimeout(sessionTimeout);
                context.signal.removeEventListener("abort", abortSession);
              }
              if (context.signal.aborted)
                throw new Error("cancelled before answer applied");
              yield pc.setRemoteDescription({ sdp: answer.sdp, type: answer.type });
              if (closed || context.signal.aborted) {
                throw new Error("cancelled while applying the answer");
              }
              let heartbeatStrikes = 0;
              const HEARTBEAT_MAX_STRIKES = 3;
              heartbeat = setInterval(() => {
                if (heartbeatInFlight)
                  return;
                heartbeatInFlight = true;
                const controller = new AbortController();
                heartbeatController = controller;
                const heartbeatTimeout = setTimeout(() => controller.abort(), HEARTBEAT_TIMEOUT_MS);
                context.fetch(`${WMA_URL}/session/heartbeat`, {
                  method: "POST",
                  signal: controller.signal,
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ session_id: answer.session_id })
                }).then((response) => __awaiter(this, void 0, void 0, function* () {
                  if (!response.ok) {
                    yield response.arrayBuffer().catch(() => void 0);
                    heartbeatStrikes++;
                    if (heartbeatStrikes >= HEARTBEAT_MAX_STRIKES && !closed && !context.signal.aborted) {
                      yield context.fail(`WMA heartbeat rejected ${heartbeatStrikes} times in a row (last status ${response.status}) \u2014 the session lease is gone`, {
                        consecutiveFailures: heartbeatStrikes,
                        lastStatus: response.status
                      });
                    }
                    return;
                  }
                  let status;
                  try {
                    status = yield response.json();
                  } catch (_a2) {
                    heartbeatStrikes++;
                    if (heartbeatStrikes >= HEARTBEAT_MAX_STRIKES && !closed && !context.signal.aborted) {
                      yield context.fail(`WMA heartbeat returned unparseable responses ${heartbeatStrikes} times in a row \u2014 the session lease is gone`, { consecutiveFailures: heartbeatStrikes });
                    }
                    return;
                  }
                  heartbeatStrikes = 0;
                  if (status.alive === false && !closed && !context.signal.aborted) {
                    yield context.fail("WMA bridge reports that the session is no longer alive");
                  }
                })).catch(() => {
                }).finally(() => {
                  clearTimeout(heartbeatTimeout);
                  if (heartbeatController === controller) {
                    heartbeatController = null;
                  }
                  heartbeatInFlight = false;
                });
              }, HEARTBEAT_INTERVAL_MS);
              return {
                sessionId: answer.session_id,
                send(message) {
                  if (channel.readyState !== "open" && channel.readyState !== "connecting") {
                    return;
                  }
                  sendPayload(JSON.stringify(message));
                },
                getConnectionInfo() {
                  return __awaiter(this, void 0, void 0, function* () {
                    if (channel.readyState !== "open") {
                      let openDeadline;
                      try {
                        yield Promise.race([
                          controlChannelOpen,
                          new Promise((_, reject) => {
                            openDeadline = setTimeout(() => reject(new Error(`WMA control channel did not open within ${NETWORK_INFO_TIMEOUT_MS / 1e3}s`)), NETWORK_INFO_TIMEOUT_MS);
                          })
                        ]);
                      } finally {
                        clearTimeout(openDeadline);
                      }
                    }
                    if (closed || channel.readyState !== "open") {
                      throw new Error("WMA control channel is not available");
                    }
                    const requestId = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
                    let timeout;
                    const runner = new Promise((resolve, reject) => {
                      timeout = setTimeout(() => {
                        const request = networkRequests.get(requestId);
                        if (!request)
                          return;
                        networkRequests.delete(requestId);
                        request.reject(new Error(`runner network info timed out after ${NETWORK_INFO_TIMEOUT_MS / 1e3}s`));
                      }, NETWORK_INFO_TIMEOUT_MS);
                      networkRequests.set(requestId, {
                        resolve: (value) => {
                          clearTimeout(timeout);
                          resolve(value);
                        },
                        reject: (error) => {
                          clearTimeout(timeout);
                          reject(error);
                        }
                      });
                    });
                    try {
                      channel.send(JSON.stringify({
                        type: NETWORK_INFO_REQUEST_TYPE,
                        request_id: requestId
                      }));
                    } catch (error) {
                      const request = networkRequests.get(requestId);
                      networkRequests.delete(requestId);
                      request === null || request === void 0 ? void 0 : request.reject(error instanceof Error ? error : new Error("WMA network probe could not be sent"));
                    }
                    const runnerPath = yield runner;
                    const browser = yield browserNetworkPath(pc, answer.session_id, runnerPath, networkProbeController.signal);
                    for (const path of [browser, runnerPath]) {
                      const local = path.localCandidate;
                      const remote = path.remoteCandidate;
                      context.diagnostic({
                        kind: "progress",
                        phase: "network-path",
                        detail: {
                          side: path.side,
                          local: local ? `${local.type}/${local.protocol} ${local.endpoint}` : "unavailable",
                          remote: remote ? `${remote.type}/${remote.protocol} ${remote.endpoint}` : "unavailable",
                          usesTurn: path.usesTurn ? "yes" : "no",
                          rttMs: path.currentRoundTripTimeMs === void 0 ? "unavailable" : Math.round(path.currentRoundTripTimeMs)
                        }
                      });
                    }
                    return { browser, runner: runnerPath };
                  });
                },
                close: teardown
              };
            } catch (exc) {
              teardown();
              throw exc;
            }
          });
        }
      });
    }
  }
});

// src/entry.mjs
var import_client = __toESM(require_src(), 1);
var import_wma = __toESM(require_wma(), 1);
var video = document.getElementById("stage-video");
var statusEl = document.getElementById("stage-status");
var overlay = document.getElementById("start-overlay");
var currentToken = null;
var conn = null;
var heartbeatTimer = null;
var stageState = "idle";
import_client.fal.config({
  proxyUrl: `${window.location.origin}/director/fal-proxy`,
  requestMiddleware: (config) => Promise.resolve({
    ...config,
    headers: { ...config.headers || {}, "x-director-token": currentToken || "" }
  })
});
function setStatus(text) {
  stageState = text;
  if (statusEl) statusEl.textContent = text;
}
function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}
function startHeartbeat(token) {
  stopHeartbeat();
  heartbeatTimer = setInterval(() => {
    fetch("/director/heartbeat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token, state: stageState })
    }).catch(() => {
    });
  }, 5e3);
}
function closeSession() {
  stopHeartbeat();
  if (conn) {
    try {
      conn.close();
    } catch {
    }
    conn = null;
  }
  currentToken = null;
  video.srcObject = null;
}
function joinSession(evt) {
  closeSession();
  currentToken = evt.token;
  setStatus("connecting");
  conn = import_client.fal.realtime.open((0, import_wma.wma)(evt.endpointId), {
    receive: ["video", "audio"],
    onState: (state) => {
      if (state === "live") setStatus("live");
    },
    onError: (err) => {
      setStatus("error");
      console.error("director session error", err);
    },
    onMedia: (stream) => {
      video.srcObject = stream;
      video.play().catch(() => {
        if (overlay) overlay.hidden = false;
      });
    }
  });
  conn.send({
    type: "configure",
    protocol_version: 1,
    prompt_version: evt.promptVersion,
    prompt: evt.prompt,
    resolution: evt.resolution,
    aspect_ratio: evt.aspectRatio
  });
  startHeartbeat(evt.token);
}
function handleEvent(evt) {
  if (evt.type === "start") {
    joinSession(evt);
  } else if (evt.type === "speak") {
    if (conn) {
      conn.send({ type: "prompt", prompt_version: evt.promptVersion, audio_url: evt.audioUrl, audio_behavior: "replace" });
    }
  } else if (evt.type === "stop") {
    closeSession();
    setStatus("idle");
  } else if (evt.type === "idle") {
    setStatus("idle");
  }
}
function connectEvents() {
  const source = new EventSource("/director/events");
  source.onmessage = (msg) => {
    try {
      handleEvent(JSON.parse(msg.data));
    } catch (err) {
      console.error("bad director event", err, msg.data);
    }
  };
  source.onerror = () => {
    setStatus("reconnecting");
  };
}
window.addEventListener("pagehide", closeSession);
window.addEventListener("beforeunload", closeSession);
if (overlay) {
  overlay.addEventListener("click", () => {
    overlay.hidden = true;
    video.play().catch(() => {
    });
  });
}
connectEvents();
