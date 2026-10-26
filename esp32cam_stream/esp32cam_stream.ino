#include "esp_camera.h"
#include <WiFi.h>
#include <ESPmDNS.h>
#include "esp_http_server.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "wifi_config.h"

const char* CAMERA_HOSTNAME = "blindcam";
bool mdnsStarted = false;
// External normally-open button: GPIO13 -> button -> GND. No SD card use.
const int BUTTON_GPIO = 13;
volatile uint32_t buttonPresses = 0;
uint32_t bootId;
int lastButtonReading = HIGH;
int stableButtonState = HIGH;
unsigned long lastButtonChange = 0;
unsigned long lastReconnect = 0;

void pollButton() {
  int reading = digitalRead(BUTTON_GPIO);
  if (reading != lastButtonReading) lastButtonChange = millis();
  if (millis() - lastButtonChange >= 50 && reading != stableButtonState) {
    stableButtonState = reading;
    if (reading == LOW) ++buttonPresses;
  }
  lastButtonReading = reading;
}

static esp_err_t button_handler(httpd_req_t *req) {
  char body[100];
  snprintf(body, sizeof(body), "{\"boot_id\":%u,\"press_count\":%u}",
           (unsigned)bootId, (unsigned)buttonPresses);
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  return httpd_resp_send(req, body, HTTPD_RESP_USE_STRLEN);
}

void startDiscovery() {
  MDNS.end();
  mdnsStarted = MDNS.begin(CAMERA_HOSTNAME);
  if (mdnsStarted) {
    MDNS.setInstanceName("blindcam");
    MDNS.addService("blindcam", "tcp", 80);
    MDNS.addServiceTxt("blindcam", "tcp", "path", "/capture");
    Serial.println("Camera hostname: http://blindcam.local/capture");
  } else {
    Serial.println("mDNS failed; will retry.");
  }
}

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

#define PART_BOUNDARY "123456789000000000000987654321"
static const char* STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

httpd_handle_t stream_httpd = NULL;
httpd_handle_t capture_httpd = NULL;

static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t *fb = NULL;
  esp_err_t res = ESP_OK;
  char part_buf[64];

  res = httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

  while (true) {
    fb = esp_camera_fb_get();
    if (!fb) {
      res = ESP_FAIL;
    } else {
      size_t hlen = snprintf(part_buf, 64, STREAM_PART, fb->len);
      res = httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
      if (res == ESP_OK) res = httpd_resp_send_chunk(req, part_buf, hlen);
      if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
      esp_camera_fb_return(fb);
    }
    if (res != ESP_OK) break;
  }
  return res;
}

static esp_err_t capture_handler(httpd_req_t *req) {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }
  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return res;
}

void startServers() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();

  config.server_port = 80;
  httpd_uri_t capture_uri = { .uri = "/capture", .method = HTTP_GET, .handler = capture_handler, .user_ctx = NULL };
  if (httpd_start(&capture_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(capture_httpd, &capture_uri);
    httpd_uri_t button_uri = { .uri = "/button", .method = HTTP_GET,
                              .handler = button_handler, .user_ctx = NULL };
    httpd_register_uri_handler(capture_httpd, &button_uri);
  }

  config.server_port = 81;
  config.ctrl_port += 1;
  httpd_uri_t stream_uri = { .uri = "/stream", .method = HTTP_GET, .handler = stream_handler, .user_ctx = NULL };
  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
  }
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
  Serial.begin(115200);
  pinMode(BUTTON_GPIO, INPUT_PULLUP);
  bootId = esp_random();

  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_LATEST;

  if (psramFound()) {
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 12;
    config.fb_count = 2;
    config.fb_location = CAMERA_FB_IN_PSRAM;
  } else {
    config.frame_size = FRAMESIZE_QVGA;
    config.jpeg_quality = 15;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", err);
    delay(3000);
    ESP.restart();
  }

  WiFi.mode(WIFI_STA);
  WiFi.setHostname(CAMERA_HOSTNAME);
  WiFi.setSleep(false);
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  startServers();
  startDiscovery();

  Serial.print("Stream:  http://");
  Serial.print(WiFi.localIP());
  Serial.println(":81/stream");
  Serial.print("Capture: http://");
  Serial.print(WiFi.localIP());
  Serial.println("/capture");
}

void loop() {
  pollButton();
  if (WiFi.status() != WL_CONNECTED) {
    if (mdnsStarted) MDNS.end();
    mdnsStarted = false;
    if (millis() - lastReconnect >= 5000) {
      WiFi.reconnect();
      lastReconnect = millis();
    }
  }
  if (WiFi.status() == WL_CONNECTED && !mdnsStarted) startDiscovery();
  delay(10);
}
