<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
header('X-Robots-Tag: noindex, nofollow');

function sendWeatherResult(bool $rain, bool $available, int $status = 200): void
{
    http_response_code($status);
    echo json_encode(
        ['rain' => $rain, 'available' => $available],
        JSON_UNESCAPED_SLASHES
    );
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET') {
    header('Allow: GET');
    sendWeatherResult(false, false, 405);
}

$regions = [
    'lefkoşa' => ['lat' => '35.1856', 'lon' => '33.3823'],
    'girne' => ['lat' => '35.3400', 'lon' => '33.3190'],
    'çatalköy' => ['lat' => '35.3470', 'lon' => '33.3670'],
    'alsancak' => ['lat' => '35.3320', 'lon' => '33.2240'],
    'lapta' => ['lat' => '35.3460', 'lon' => '33.1760'],
];

function detectRainForCurrentPeriod(string $body, int $now): ?bool
{
    $forecast = json_decode($body, true);
    $series = $forecast['properties']['timeseries'] ?? null;
    if (!is_array($series) || !$series) {
        return null;
    }

    $nearest = null;
    $nearestDistance = PHP_INT_MAX;
    foreach ($series as $item) {
        $timestamp = isset($item['time']) ? strtotime((string) $item['time']) : false;
        if ($timestamp === false) {
            continue;
        }
        $distance = abs($timestamp - $now);
        if ($distance < $nearestDistance) {
            $nearestDistance = $distance;
            $nearest = $item;
        }
    }

    if ($nearest === null || $nearestDistance > 5400) {
        return null;
    }

    $nextHour = $nearest['data']['next_1_hours'] ?? null;
    if (!is_array($nextHour)) {
        return false;
    }

    $symbol = strtolower((string) ($nextHour['summary']['symbol_code'] ?? ''));
    if (preg_match('/rain|drizzle|thunder|freezingrain/', $symbol) === 1) {
        return true;
    }

    if (preg_match('/snow|sleet/', $symbol) === 1) {
        return false;
    }

    $amount = $nextHour['details']['precipitation_amount'] ?? null;
    return is_numeric($amount) && (float) $amount >= 0.1;
}

function loadWeatherCache(string $path): ?array
{
    $raw = @file_get_contents($path);
    if (!is_string($raw) || $raw === '') {
        return null;
    }
    $cache = json_decode($raw, true);
    return is_array($cache) ? $cache : null;
}

function saveWeatherCache(string $path, array $data): void
{
    $json = json_encode($data, JSON_UNESCAPED_SLASHES);
    if (is_string($json)) {
        @file_put_contents($path, $json, LOCK_EX);
    }
}

function readHeaderCacheExpiry(array $headers, int $now): int
{
    $expiry = isset($headers['expires']) ? strtotime($headers['expires']) : false;
    if ($expiry !== false && $expiry > $now) {
        return $expiry;
    }
    return $now + 900;
}

if (!function_exists('curl_multi_init') || !function_exists('curl_init')) {
    sendWeatherResult(false, false, 503);
}

$cacheDir = rtrim(sys_get_temp_dir(), DIRECTORY_SEPARATOR)
    . DIRECTORY_SEPARATOR . 'bulut-dede-met-weather-' . substr(hash('sha256', __DIR__), 0, 12);
if (!is_dir($cacheDir) && !@mkdir($cacheDir, 0700, true) && !is_dir($cacheDir)) {
    sendWeatherResult(false, false, 503);
}
$lock = @fopen($cacheDir . DIRECTORY_SEPARATOR . 'refresh.lock', 'c');
if (!is_resource($lock) || !@flock($lock, LOCK_EX)) {
    sendWeatherResult(false, false, 503);
}

$now = time();
$cacheByRegion = [];
$pending = [];
foreach ($regions as $name => $location) {
    $cachePath = $cacheDir . DIRECTORY_SEPARATOR . $name . '.json';
    $cache = loadWeatherCache($cachePath);
    $cacheByRegion[$name] = ['path' => $cachePath, 'data' => $cache];
    if (!is_array($cache) || !isset($cache['expires_at'], $cache['checked_at'], $cache['rain'])) {
        $pending[$name] = $location;
    } elseif ((int) $cache['expires_at'] <= $now) {
        $pending[$name] = $location;
    }
}

$multi = curl_multi_init();
$handles = [];
$headersByRegion = [];
foreach ($pending as $name => $location) {
    $headersByRegion[$name] = [];
    $headerKey = $name;
    $url = 'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat='
        . rawurlencode($location['lat']) . '&lon=' . rawurlencode($location['lon']);
    $headers = [];
    $handle = curl_init($url);
    $options = [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 3,
        CURLOPT_CONNECTTIMEOUT => 3,
        CURLOPT_TIMEOUT => 6,
        CURLOPT_ENCODING => '',
        CURLOPT_SSL_VERIFYPEER => true,
        CURLOPT_USERAGENT => 'bulutdedeelektrik.com (+https://bulutdedeelektrik.com/)',
        CURLOPT_HTTPHEADER => ['Accept: application/json'],
        CURLOPT_HEADERFUNCTION => static function ($curl, string $line) use (&$headersByRegion, $headerKey): int {
            $length = strlen($line);
            if (strncmp(strtoupper($line), 'HTTP/', 5) === 0) {
                $headersByRegion[$headerKey] = [];
            } else {
                $parts = explode(':', $line, 2);
                if (count($parts) === 2) {
                    $headersByRegion[$headerKey][strtolower(trim($parts[0]))] = trim($parts[1]);
                }
            }
            return $length;
        },
    ];
    $cached = $cacheByRegion[$name]['data'];
    if (is_array($cached) && !empty($cached['last_modified'])) {
        $options[CURLOPT_HTTPHEADER][] = 'If-Modified-Since: ' . $cached['last_modified'];
    }
    curl_setopt_array($handle, $options);
    curl_multi_add_handle($multi, $handle);
    $handles[$name] = ['handle' => $handle];
}

$running = null;
do {
    $multiStatus = curl_multi_exec($multi, $running);
    if ($running > 0) {
        $selected = curl_multi_select($multi, 1.0);
        if ($selected === -1) {
            usleep(10000);
        }
    }
} while ($multiStatus === CURLM_OK && $running > 0);

foreach ($handles as $name => $entry) {
    $handle = $entry['handle'];
    $cached = $cacheByRegion[$name]['data'];
    $status = (int) curl_getinfo($handle, CURLINFO_RESPONSE_CODE);
    $body = curl_multi_getcontent($handle);
    $responseHeaders = $headersByRegion[$name] ?? [];

    if ($status === 304 && is_array($cached)) {
        $cached['checked_at'] = $now;
        $cached['expires_at'] = readHeaderCacheExpiry($responseHeaders, $now);
        if (!empty($responseHeaders['last-modified'])) {
            $cached['last_modified'] = $responseHeaders['last-modified'];
        }
        saveWeatherCache($cacheByRegion[$name]['path'], $cached);
        $cacheByRegion[$name]['data'] = $cached;
    } elseif ($status >= 200 && $status < 300 && is_string($body)) {
        $rain = detectRainForCurrentPeriod($body, $now);
        if ($rain !== null) {
            $cached = [
                'rain' => $rain,
                'checked_at' => $now,
                'expires_at' => readHeaderCacheExpiry($responseHeaders, $now),
                'last_modified' => $responseHeaders['last-modified'] ?? '',
            ];
            saveWeatherCache($cacheByRegion[$name]['path'], $cached);
            $cacheByRegion[$name]['data'] = $cached;
        }
    }

    curl_multi_remove_handle($multi, $handle);
    curl_close($handle);
}
curl_multi_close($multi);

$anyAvailable = false;
$anyRain = false;
foreach ($cacheByRegion as $region) {
    $data = $region['data'];
    if (!is_array($data) || !isset($data['rain'], $data['checked_at'])) {
        continue;
    }
    if ((int) $data['checked_at'] < $now - 1800) {
        continue;
    }
    $anyAvailable = true;
    $anyRain = $anyRain || $data['rain'] === true;
}

@flock($lock, LOCK_UN);
@fclose($lock);
sendWeatherResult($anyRain, $anyAvailable);
