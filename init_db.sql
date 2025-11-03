-- 初始化数据库表结构

-- 创建分类表
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE COMMENT '分类名称',
    description TEXT COMMENT '分类描述',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分类表';

-- 创建账单表
CREATE TABLE IF NOT EXISTS bills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    amount DECIMAL(10, 2) NOT NULL COMMENT '金额',
    type ENUM('income', 'expense') NOT NULL COMMENT '类型：收入或支出',
    category_id INT COMMENT '分类ID',
    description TEXT COMMENT '描述',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账单表';

-- 插入一些默认分类
INSERT INTO categories (name, description) VALUES
('餐饮', '日常用餐、外卖等餐饮消费'),
('交通', '公交、地铁、打车、油费等交通相关费用'),
('购物', '日常用品、服装、电子产品等购物消费'),
('娱乐', '电影、游戏、旅游等娱乐支出'),
('医疗', '看病、买药等医疗相关费用'),
('教育', '培训、书籍、课程等教育支出'),
('工资', '工作收入'),
('奖金', '奖金、津贴等额外收入'),
('投资', '投资收益、分红等'),
('其他', '其他未分类的收入或支出')
ON DUPLICATE KEY UPDATE name=name;

