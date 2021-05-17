# migrations 
create_db = '''
CREATE DATABASE  IF NOT EXISTS `choco_update` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `choco_update`;
'''

create_tbl_package = '''
--
-- Table structure for table `package`
--

CREATE TABLE IF NOT EXISTS `package` (
  `id` INTEGER PRIMARY KEY AUTOINCREMENT,
  `name` varchar(45) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `choco_id` varchar(45) NOT NULL,
  -- MySQL -- PRIMARY KEY (`id`),
  UNIQUE (`choco_id`)
  -- MySQL -- UNIQUE KEY `choco_id_UNIQUE` (`choco_id`)
) 
-- ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

'''

create_tbl_package_update = '''
--
-- Table structure for table `pkg_update`
--

CREATE TABLE IF NOT EXISTS `pkg_update` (
  `package_id` INTEGER NOT NULL,
  `version` varchar(45) NOT NULL,
  `update_timestamp` timestamp NULL DEFAULT NULL,
  `fetch_timestamp` timestamp NOT NULL,
  `status_id` int NOT NULL,
  PRIMARY KEY (`package_id`,`version`),
  -- MySQL -- KEY `fk_status_id_idx` (`status_id`),
  FOREIGN KEY (`package_id`) REFERENCES `package` (`id`) ON DELETE CASCADE,
  FOREIGN KEY (`status_id`) REFERENCES `status` (`id`)
  -- MySQL -- CONSTRAINT `fk_package_id` FOREIGN KEY (`package_id`) REFERENCES `package` (`id`) ON DELETE CASCADE,
  -- MySQL -- CONSTRAINT `fk_status_id` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`)
) 
-- ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

'''


create_tbl_status = '''
--
-- Table structure for table `status`
--

CREATE TABLE IF NOT EXISTS `status` (
  `id` INTEGER PRIMARY KEY AUTOINCREMENT,
  `name` varchar(45) NOT NULL
)
-- ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
'''

'''-- MySQL --
 CREATE TABLE IF NOT EXISTS `status` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(45) NOT NULL,
  PRIMARY KEY (`id`)
)
'''

# seeders 
insert_tbl_status = '''
INSERT INTO `status` VALUES (1,'pending'),(2,'updated'),(3,'skipped'),(4,'deleted');
'''

# MySQL
'''
LOCK TABLES `status` WRITE;
/*!40000 ALTER TABLE `status` DISABLE KEYS */;
INSERT INTO `status` VALUES (1,'pending'),(2,'updated'),(3,'skipped'),(4,'deleted');
/*!40000 ALTER TABLE `status` ENABLE KEYS */;
UNLOCK TABLES;
'''