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
-- Table structure for table `commodity`
--

DROP TABLE IF EXISTS `commodity`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `commodity` (
  `commodityID` int NOT NULL AUTO_INCREMENT,
  `commodityName` varchar(45) NOT NULL,
  `commodityPrice` float NOT NULL,
  `commodityCost` float NOT NULL,
  `commodityRamin` int NOT NULL,
  `supplier_supplierID` int NOT NULL,
  PRIMARY KEY (`commodityID`,`supplier_supplierID`),
  KEY `fk_commodity_supplier1_idx` (`supplier_supplierID`),
  CONSTRAINT `fk_commodity_supplier1` FOREIGN KEY (`supplier_supplierID`) REFERENCES `supplier` (`supplierID`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `commodity`
--

LOCK TABLES `commodity` WRITE;
/*!40000 ALTER TABLE `commodity` DISABLE KEYS */;
INSERT INTO `commodity` VALUES (1,'550ml瓶装矿泉水',2.5,1.2,1999,1),(2,'500g袋装大米（东北稻花香）',12,6.8,800,4),(3,'12枚装鸡蛋（散养）',28,15,160,2),(4,'250g袋装坚果（混合）',18,8.5,290,2),(5,'1.5L装食用大豆油',65,32,46,4),(6,'200g盒装酸奶（原味）',6.5,3,500,1),(7,'1kg装洗衣液（柔顺型）',28,12,120,3),(8,'500ml装洗发水（防脱型）',35,18,76,3),(9,'50g装香皂（植物精油）',9,4,150,3),(11,'小熊饼干',7,4,100,4),(12,'桶装方便面',5,2.5,200,1);
/*!40000 ALTER TABLE `commodity` ENABLE KEYS */;
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
