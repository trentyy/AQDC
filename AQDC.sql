-- MySQL dump 10.18  Distrib 10.3.27-MariaDB, for debian-linux-gnueabihf (armv8l)
--
-- Host: localhost    Database: AQDC
-- ------------------------------------------------------
-- Server version	10.3.27-MariaDB-0+deb10u1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `cwb_Taichung`
--

DROP TABLE IF EXISTS `cwb_Taichung`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cwb_Taichung` (
  `obsTime` datetime NOT NULL,
  `lat` float DEFAULT NULL,
  `lon` float DEFAULT NULL,
  `locationName` varchar(8) DEFAULT NULL,
  `TEMP` float DEFAULT NULL,
  `PRES` float DEFAULT NULL,
  `H_F10` float DEFAULT NULL,
  `H_UVI` tinyint(4) DEFAULT NULL,
  `Weather` varchar(16) DEFAULT NULL,
  `CITY` varchar(8) DEFAULT NULL,
  `TOWN` varchar(8) DEFAULT NULL,
  `HUMD` float DEFAULT NULL,
  PRIMARY KEY (`obsTime`),
  KEY `obsTime` (`obsTime`),
  KEY `TEMP` (`TEMP`),
  KEY `HUMD` (`HUMD`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `epa_Taichung`
--

DROP TABLE IF EXISTS `epa_Taichung`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `epa_Taichung` (
  `time` datetime NOT NULL,
  `PM2_5` smallint(5) unsigned DEFAULT NULL,
  `PM10` smallint(5) unsigned DEFAULT NULL,
  PRIMARY KEY (`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;

--

--
-- Table structure for table `sensor_data`
--

DROP TABLE IF EXISTS `sensor_data`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sensor_data` (
  `time` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `temperture` double DEFAULT NULL,
  `humidity` double DEFAULT NULL,
  `CO2` int(11) DEFAULT NULL,
  `TVOC` int(11) DEFAULT NULL,
  `PM1` smallint(5) unsigned DEFAULT NULL,
  `PM2_5` smallint(5) unsigned DEFAULT NULL,
  `PM10` smallint(5) unsigned DEFAULT NULL,
  PRIMARY KEY (`time`),
  KEY `temperture` (`temperture`),
  KEY `humidity` (`humidity`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
/*!40101 SET character_set_client = @saved_cs_client */;


/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2020-12-26 10:54:41
