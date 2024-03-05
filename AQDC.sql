-- --------------------------------------------------------
-- 主機:                           192.168.31.15
-- 伺服器版本:                        10.11.6-MariaDB-0+deb12u1 - Debian 12
-- 伺服器作業系統:                      debian-linux-gnu
-- HeidiSQL 版本:                  12.3.0.6589
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- 傾印 AQDC 的資料庫結構
CREATE DATABASE IF NOT EXISTS `AQDC` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci */;
USE `AQDC`;

-- 傾印  資料表 AQDC.cwa_Taipei 結構
CREATE TABLE IF NOT EXISTS `cwa_Taipei` (
  `DateTime` datetime NOT NULL,
  `StationName` varchar(8) DEFAULT NULL,
  `Weather` varchar(16) DEFAULT NULL,
  `Precipitation` float DEFAULT NULL,
  `WindDirection` float DEFAULT NULL,
  `WindSpeed` float DEFAULT NULL,
  `AirTemperature` float DEFAULT NULL,
  `RelativeHumidity` float DEFAULT NULL,
  `AirPressure` float DEFAULT NULL,
  PRIMARY KEY (`DateTime`) USING BTREE,
  KEY `obsTime` (`DateTime`) USING BTREE,
  KEY `TEMP` (`AirTemperature`) USING BTREE,
  KEY `HUMD` (`RelativeHumidity`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 取消選取資料匯出。

-- 傾印  資料表 AQDC.epa_Taipei 結構
CREATE TABLE IF NOT EXISTS `epa_Taipei` (
  `time` datetime NOT NULL,
  `PM2_5` smallint(5) unsigned DEFAULT NULL,
  `PM10` smallint(5) unsigned DEFAULT NULL,
  PRIMARY KEY (`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 取消選取資料匯出。

-- 傾印  資料表 AQDC.home_dht22 結構
CREATE TABLE IF NOT EXISTS `home_dht22` (
  `time` datetime NOT NULL,
  `temperature` float NOT NULL,
  `humidity` float NOT NULL,
  PRIMARY KEY (`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 取消選取資料匯出。

-- 傾印  資料表 AQDC.home_ds18b20 結構
CREATE TABLE IF NOT EXISTS `home_ds18b20` (
  `time` datetime NOT NULL,
  `temperature` float NOT NULL DEFAULT 0,
  PRIMARY KEY (`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 取消選取資料匯出。

-- 傾印  資料表 AQDC.home_mhz19b 結構
CREATE TABLE IF NOT EXISTS `home_mhz19b` (
  `time` datetime NOT NULL,
  `temperature` float NOT NULL,
  `co2` float NOT NULL,
  PRIMARY KEY (`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 取消選取資料匯出。

-- 傾印  資料表 AQDC.home_pms7003 結構
CREATE TABLE IF NOT EXISTS `home_pms7003` (
  `time` datetime NOT NULL,
  `pm1` int(11) NOT NULL DEFAULT 0,
  `pm2_5` int(11) NOT NULL DEFAULT 0,
  `pm10` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 取消選取資料匯出。

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
