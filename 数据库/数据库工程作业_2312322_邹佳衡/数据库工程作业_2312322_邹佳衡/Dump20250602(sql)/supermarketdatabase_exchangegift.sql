-- MySQL dump 10.13  Distrib 8.0.19, for Win64 (x86_64)
--
-- Host: localhost    Database: supermarketdatabase
-- ------------------------------------------------------
-- Server version	8.0.19

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `exchangegift`
--

DROP TABLE IF EXISTS `exchangegift`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `exchangegift` (
  `custom_customID` int NOT NULL,
  `gift_giftID` int NOT NULL,
  `exchangeTime` datetime(3) NOT NULL,
  `exchangeNum` int NOT NULL,
  PRIMARY KEY (`custom_customID`,`gift_giftID`,`exchangeTime`),
  KEY `fk_exchangegift_gift` (`gift_giftID`),
  CONSTRAINT `fk_exchangegift_custom` FOREIGN KEY (`custom_customID`) REFERENCES `custom` (`customID`),
  CONSTRAINT `fk_exchangegift_gift` FOREIGN KEY (`gift_giftID`) REFERENCES `gift` (`giftID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `exchangegift`
--

LOCK TABLES `exchangegift` WRITE;
/*!40000 ALTER TABLE `exchangegift` DISABLE KEYS */;
INSERT INTO `exchangegift` VALUES (1,5,'2025-06-01 19:39:06.000',1),(1,5,'2025-06-01 19:40:53.000',1),(2,5,'2025-06-01 19:41:42.000',1);
/*!40000 ALTER TABLE `exchangegift` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-06-02 20:05:37
