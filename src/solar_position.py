# -*- coding: utf-8 -*-
r"""태양 위치 계산 및 그늘 분석 모듈.
시간대·계절별 태양각도를 계산하여 건물/가로수 그늘을 추정.
"""
import numpy as np
from datetime import datetime, timedelta
import pytz

# 대구의 좌표 (EPSG:5179 → WGS84)
DAEGU_LAT = 35.8721  # 위도
DAEGU_LON = 128.5953  # 경도
TIMEZONE = pytz.timezone('Asia/Seoul')

def solar_position_simple(lat, lon, dt):
    """간단한 태양 위치 계산 (고도각, 방위각).

    Parameters
    ----------
    lat : float
        위도 (도)
    lon : float
        경도 (도)
    dt : datetime
        관측 시간 (UTC)

    Returns
    -------
    tuple
        (altitude, azimuth) in degrees
    """
    # 줄리안 일 계산
    year, month, day = dt.year, dt.month, dt.day
    hour, minute, second = dt.hour, dt.minute, dt.second

    # NOAA 태양 위치 알고리즘 (간단 버전)
    J = day - 32.18 + (10.13 * 24 - hour - minute / 60 - second / 3600) / 24
    M = 6.2401699 + 0.01720197 * (367 * year - 7 * (year + (month + 9) // 12) // 4 + 275 * month // 9 + day - 724468)
    M_deg = np.degrees(M % (2 * np.pi))

    # 방정식의 시간
    lambda_rad = (1.914602 - 0.004817 * M_deg - 0.040695 * M_deg) * np.sin(np.radians(M_deg))
    lambda_rad += (0.019993 - 0.000101 * M_deg) * np.sin(2 * np.radians(M_deg))
    lambda_rad += 0.000029 * np.sin(3 * np.radians(M_deg))
    lambda_rad += M_deg + 102.93735

    eot = 229.2 * (0.000075 + 0.001868 * np.cos(np.radians(M_deg)) - 0.032077 * np.sin(np.radians(M_deg))
                   - 0.014615 * np.cos(2 * np.radians(M_deg)) - 0.040849 * np.sin(2 * np.radians(M_deg)))

    # 지방 시간 (분)
    local_time = hour * 60 + minute + second / 60
    lst = local_time + eot + 4 * lon

    # 시간각 (시간)
    h = (lst / 60 - 12)

    # 태양 적위 (rad)
    dec_rad = np.radians(23.44) * np.sin(np.radians(lambda_rad - 90))

    # 고도각 (rad)
    alt_rad = np.arcsin(np.sin(np.radians(lat)) * np.sin(dec_rad) +
                        np.cos(np.radians(lat)) * np.cos(dec_rad) * np.cos(np.radians(h * 15)))
    altitude = np.degrees(alt_rad)

    # 방위각 (rad) - 남쪽 기준 (0도)
    az_rad = np.arctan2(
        np.sin(np.radians(h * 15)),
        np.cos(np.radians(h * 15)) * np.sin(np.radians(lat)) - np.tan(dec_rad) * np.cos(np.radians(lat))
    )
    azimuth = (np.degrees(az_rad) + 180) % 360

    return altitude, azimuth

def shadow_length(building_height, sun_altitude):
    """태양 고도각에 따른 그림자 길이.

    Parameters
    ----------
    building_height : float
        건물 높이 (m)
    sun_altitude : float
        태양 고도각 (도)

    Returns
    -------
    float
        그림자 길이 (m). 고도각이 음수(태양이 지평선 아래)면 무한대 반환
    """
    if sun_altitude <= 0:
        return np.inf

    return building_height / np.tan(np.radians(sun_altitude))

def shade_coverage_summer(lat, lon, hour_list=None):
    """여름 하지(6월 21일)의 시간대별 그늘 커버율.

    Parameters
    ----------
    lat : float
        위도
    lon : float
        경도
    hour_list : list
        계산할 시간 [0, 6, 9, 12, 15, 18, ...]

    Returns
    -------
    dict
        hour → shade_coverage (0~1)
    """
    if hour_list is None:
        hour_list = list(range(6, 19))  # 06:00 ~ 18:00

    # 여름 하지 (UTC로 변환)
    summer_date = datetime(2024, 6, 21, tzinfo=TIMEZONE)

    shade_map = {}
    for hour in hour_list:
        # 서울 시간 → UTC
        dt_local = summer_date.replace(hour=hour, minute=0, second=0)
        dt_utc = dt_local.astimezone(pytz.UTC)

        altitude, azimuth = solar_position_simple(lat, lon, dt_utc)

        # 고도각이 높을수록 그늘 적음
        # coverage = max(0, 1 - altitude / 80)
        if altitude > 0:
            coverage = max(0, 1 - altitude / 60)  # 60도 기준
        else:
            coverage = 1.0  # 해가 진 경우

        shade_map[hour] = coverage

    return shade_map

def test_solar_calculation():
    """태양 위치 계산 테스트"""
    print("=" * 60)
    print("태양 위치 계산 테스트 (대구, 여름 하지)")
    print("=" * 60)

    summer_date = datetime(2024, 6, 21, tzinfo=TIMEZONE)

    for hour in range(6, 20):
        dt_local = summer_date.replace(hour=hour, minute=0, second=0)
        dt_utc = dt_local.astimezone(pytz.UTC)

        alt, azi = solar_position_simple(DAEGU_LAT, DAEGU_LON, dt_utc)

        # 건물 그림자
        shadow_10m = shadow_length(10, alt)
        shadow_20m = shadow_length(20, alt)

        print(f"{hour:02d}:00 | 고도: {alt:6.2f}° | 방위: {azi:6.2f}° | "
              f"그림자(10m): {shadow_10m:8.1f}m | 그림자(20m): {shadow_20m:8.1f}m")

if __name__ == "__main__":
    test_solar_calculation()
