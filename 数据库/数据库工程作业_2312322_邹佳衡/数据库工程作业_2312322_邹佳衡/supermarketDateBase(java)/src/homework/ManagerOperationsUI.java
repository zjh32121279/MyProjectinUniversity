package homework;

import java.awt.BorderLayout;
import java.awt.Dimension;
import java.awt.Font;
import java.awt.GridLayout;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.regex.Pattern;

import javax.swing.*;

public class ManagerOperationsUI {
	public ManagerOperationsUI() {        
        // 创建主窗口
        JFrame frame = new JFrame("经营者管理界面");
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setSize(600, 1000); // 增加窗口高度以适应新控件
        frame.setLayout(new BorderLayout());

        // 创建面板
        JPanel panel = new JPanel();
        panel.setLayout(new GridLayout(32, 2, 5, 5)); // 设置网格布局

        // 设置边距
        panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));

        // 聘用员工部分
        JLabel hireEmployeeNameLabel = new JLabel("请输入新员工姓名: ");
        JTextField hireEmployeeNameField = new JTextField();
        panel.add(hireEmployeeNameLabel);
        panel.add(hireEmployeeNameField);

        JLabel hireEmployeeIdCardLabel = new JLabel("请输入新员工身份证号: ");
        JTextField hireEmployeeIdCardField = new JTextField();
        panel.add(hireEmployeeIdCardLabel);
        panel.add(hireEmployeeIdCardField);

        JLabel hireEmployeePhoneLabel = new JLabel("请输入新员工电话号码: ");
        JTextField hireEmployeePhoneField = new JTextField();
        panel.add(hireEmployeePhoneLabel);
        panel.add(hireEmployeePhoneField);

        JLabel hireEmployeeSalaryLabel = new JLabel("请输入新员工薪水: ");
        JTextField hireEmployeeSalaryField = new JTextField();
        panel.add(hireEmployeeSalaryLabel);
        panel.add(hireEmployeeSalaryField);
        
        JLabel hireEmployeePasswordLabel = new JLabel("请输入员工登录密码：");
        JPasswordField hireEmployeePasswordField = new JPasswordField();
        panel.add(hireEmployeePasswordLabel);
        panel.add(hireEmployeePasswordField);
        
        JLabel hireEmployeePasswordAgainLabel =new JLabel("再次确认密码：");
        JPasswordField hireEmployeePasswordAgainField =new JPasswordField();
        panel.add(hireEmployeePasswordAgainLabel);
        panel.add(hireEmployeePasswordAgainField);
        
        JLabel hireEmployeeOfficeLabel = new JLabel("请输入新员工职位：");
        JTextField hireEmployeeOfficeField = new JTextField();
        panel.add(hireEmployeeOfficeLabel);
        panel.add(hireEmployeeOfficeField);

        JLabel hireEmployeeID = new JLabel("生成员工号：");
        JTextField hireShowEmployeeID =new JTextField();
        hireShowEmployeeID.setEditable(false);
        JButton hireEmployeeButton = new JButton("聘用员工");
        
        hireEmployeeButton.addActionListener(new ActionListener() {
			
        	@Override
			public void actionPerformed(ActionEvent e) {
				String name = hireEmployeeNameField.getText();
                String idCard = hireEmployeeIdCardField.getText();
                String phone = hireEmployeePhoneField.getText();
                String salaryStr = hireEmployeeSalaryField.getText();
                String password1 = hireEmployeePasswordField.getText();
                String password2 = hireEmployeePasswordAgainField.getText();
                String office = hireEmployeeOfficeField.getText();
                Integer officeID = null;

                if (!isValidName(name)) {
                    JOptionPane.showMessageDialog(frame, "姓名只能包含汉字或字母", "输入错误", JOptionPane.ERROR_MESSAGE);
                    return;
                }
                
                if (!isValidIdCard(idCard)) {
                    JOptionPane.showMessageDialog(frame, "身份证号不符合中国要求的格式", "输入错误", JOptionPane.ERROR_MESSAGE);
                    return;
                }
                
                if (!isValidPhone(phone)) {
                    JOptionPane.showMessageDialog(frame, "电话号码只能包含数字、#和*", "输入错误", JOptionPane.ERROR_MESSAGE);
                    return;
                }
                
                if (!isValidInt(salaryStr)) {
                    JOptionPane.showMessageDialog(frame, "薪水只能是数字", "输入错误", JOptionPane.ERROR_MESSAGE);
                    return;
                }
                
                int salary = Integer.parseInt(salaryStr);
                
                if (!isValidPassword(password1)||!isValidPassword(password2)||!password1.equals(password2)) {
                    JOptionPane.showMessageDialog(frame, "密码可以是数字或字母，最多11位", "输入错误", JOptionPane.ERROR_MESSAGE);
                    return;
                }
                
                if (!isValidOffice(office)) {
                    JOptionPane.showMessageDialog(frame, "职位无效，请选择正确的职位", "输入错误", JOptionPane.ERROR_MESSAGE);
                    return;
                }
                //插入内容
                String sql1 = "select * from office where officeName = ?";
                Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql1);
                    pstmt.setString(1, office);

                    // 执行查询
                    rs = pstmt.executeQuery();
                    JOptionPane.showMessageDialog(frame, "已添加员工信息");
                    // 显示结果
                    if(rs.next()) {
                    	officeID = rs.getInt("officeID");
                    }
                } catch (SQLException e1) {
                    e1.printStackTrace();
                    JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                } finally {
                    try {
                        if (rs != null) rs.close();
                        if (pstmt != null) pstmt.close();
                    } catch (SQLException e1) {
                        e1.printStackTrace();
                    }
                }
                
                String sql2 = "insert into staff (staffName,staffIdentNum,staffPhone,staffWage,staffPassword,office_officeID)"
                		+ " value (?,?,?,?,?,?)";
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql2);
                    pstmt.setString(1, name);
                    pstmt.setString(2,idCard);
                    pstmt.setString(3, phone);
                    pstmt.setInt(4, salary);
                    pstmt.setString(5,password1);
                    pstmt.setInt(6, officeID);

                    // 执行查询
                    int cout = pstmt.executeUpdate();
                    JOptionPane.showMessageDialog(frame, "已删除员工信息");
                } catch (SQLException e1) {
                    e1.printStackTrace();
                    JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                } finally {
                    try {
                        if (rs != null) rs.close();
                        if (pstmt != null) pstmt.close();
                    } catch (SQLException e1) {
                        e1.printStackTrace();
                    }
                }

                // 生成唯一员工编号
                Integer employeeID = generateUniqueEmployeeID(frame,name,idCard,phone,Integer.parseInt(salaryStr),password1);
                hireShowEmployeeID.setText(employeeID.toString());
                
            }
		});
        
        panel.add(new JLabel()); // 空白占位符
        panel.add(hireEmployeeButton);
        panel.add(hireEmployeeID);
        panel.add(hireShowEmployeeID);

        // 开除员工部分
        JLabel fireEmployeeIdLabel = new JLabel("请输入要开除的员工编号: ");
        JTextField fireEmployeeIdField = new JTextField();
        panel.add(fireEmployeeIdLabel);
        panel.add(fireEmployeeIdField);

        JButton fireEmployeeButton = new JButton("开除员工");
        
        fireEmployeeButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				if(!isValidEmployeeNum(fireEmployeeIdField.getText())) {
					JOptionPane.showMessageDialog(null, "员工号只能是整数", "错误", JOptionPane.ERROR_MESSAGE);
					return ;
				}
				Integer employeeID = Integer.parseInt(fireEmployeeIdField.getText());
				String sql = "delete from staff where staffID = ?";
				Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql);
                    pstmt.setInt(1, employeeID);

                    // 执行查询
                    int result = pstmt.executeUpdate();
                } catch (SQLException e1) {
                    e1.printStackTrace();
                    JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                } finally {
                    try {
                        if (rs != null) rs.close();
                        if (pstmt != null) pstmt.close();
                    } catch (SQLException e1) {
                        e1.printStackTrace();
                    }
                }
			}
		});
        
        panel.add(new JLabel()); // 空白占位符
        panel.add(fireEmployeeButton);

        // 查询员工信息部分
        JLabel queryEmployeeIdLabel = new JLabel("请输入要查询的员工编号: ");
        JTextField queryEmployeeIdField = new JTextField();
        panel.add(queryEmployeeIdLabel);
        panel.add(queryEmployeeIdField);

        JButton queryEmployeeInfoButton = new JButton("查询员工信息"); 
        
        queryEmployeeInfoButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				if(!isValidEmployeeNum(queryEmployeeIdField.getText())) {
					JOptionPane.showMessageDialog(null, "员工号只能是整数", "错误", JOptionPane.ERROR_MESSAGE);
					return;
				}
				Integer employeeID = Integer.parseInt(queryEmployeeIdField.getText());
				String sql1 = "select * from staff where staffID = ?";
				String sql2 = "select officeName from staff,office where officeID = office_officeID and staffID = ?";
				
				Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql1);
                    pstmt.setInt(1, employeeID);
                    
                    rs = pstmt.executeQuery();
                    StringBuilder result = new StringBuilder();
                    if(rs.next()) {
                    	int ID = rs.getInt("staffID");
                    	String name = rs.getString("staffName");
                    	String identNum = rs.getString("staffIdentNum");
                    	String phone = rs.getString("staffPhone");
                    	int wage = rs.getInt("staffWage");
                    	
                    	result.append("编号：").append(ID).append("  姓名:").append(name).append("  身份证号：").append(identNum)
                    		  .append("  电话：").append(phone).append("  工资：").append(wage).append("元  ");
                    }
                    pstmt = connection.prepareStatement(sql2);
                    pstmt.setInt(1, employeeID);
                    
                    rs.close();
                    rs = pstmt.executeQuery();
                    if(rs.next()) {
                    	String office = rs.getString("officeName");
                    	
                    	result.append("职务：").append(office).append("\n");
                    }
                    JTextArea resultArea = new JTextArea(result.toString());
                    resultArea.setFont(new Font("Monospaced", Font.PLAIN, 12));
                    resultArea.setLineWrap(true);
                    resultArea.setWrapStyleWord(true);
                    JScrollPane scrollPane = new JScrollPane(resultArea);
                    scrollPane.setPreferredSize(new Dimension(1000, 400)); // 设置滚动窗格的首选大小
                    JOptionPane.showMessageDialog(frame, scrollPane, "查询结果", JOptionPane.INFORMATION_MESSAGE);
                } catch (SQLException e1) {
                    e1.printStackTrace();
                    JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                } finally {
                    try {
                        if (rs != null) rs.close();
                        if (pstmt != null) pstmt.close();
                    } catch (SQLException e1) {
                        e1.printStackTrace();
                    }
                }
			}
		});
        
        panel.add(new JLabel()); // 空白占位符
        panel.add(queryEmployeeInfoButton);

        // 查询商品信息部分
        JLabel queryAProductInfoLabel = new JLabel("请输入商品编号：");
        JTextField queryAProductInfoField = new JTextField();
        JButton queryAProductInfoButton = new JButton("查询商品信息");
        
        queryAProductInfoButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				if(!isValidEmployeeNum(queryAProductInfoField.getText())) {
					JOptionPane.showMessageDialog(null, "商品号只能是整数", "错误", JOptionPane.ERROR_MESSAGE);
					return;
				}
				Integer commodityID = Integer.parseInt(queryAProductInfoField.getText());
				String sql1 = "select * from commodity where commodityID = ?";
				String sql2 = "select supplierName from supplier,commodity where supplierID = supplier_supplierID and commodityID = ?";
				Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql1);
                    pstmt.setInt(1, commodityID);
                    
                    rs = pstmt.executeQuery();
                    StringBuilder result = new StringBuilder();
                    if(rs.next()) {
                    	int ID = rs.getInt("commodityID");
                    	String name = rs.getString("commodityName");
                    	float price = rs.getFloat("commodityPrice");
                    	float cost = rs.getFloat("commodityCost");
                    	int ramin = rs.getInt("commodityRamin");
                    	
                    	result.append("编号：").append(ID).append("  名称:").append(name).append("  价格：").append(price)
                    		  .append("  成本：").append(cost).append("  库存：").append(ramin).append("件  ");
                    }
                    pstmt = connection.prepareStatement(sql2);
                    pstmt.setInt(1, commodityID);
                    
                    rs.close();
                    rs = pstmt.executeQuery();
                    if(rs.next()) {
                    	String supplier = rs.getString("supplierName");
                    	
                    	result.append("供货商：").append(supplier).append("\n");
                    }
                    JTextArea resultArea = new JTextArea(result.toString());
                    resultArea.setFont(new Font("Monospaced", Font.PLAIN, 12));
                    resultArea.setLineWrap(true);
                    resultArea.setWrapStyleWord(true);
                    JScrollPane scrollPane = new JScrollPane(resultArea);
                    scrollPane.setPreferredSize(new Dimension(1000, 400)); // 设置滚动窗格的首选大小
                    JOptionPane.showMessageDialog(frame, scrollPane, "查询结果", JOptionPane.INFORMATION_MESSAGE);
                }
                    catch (SQLException e1) {
                        e1.printStackTrace();
                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                    } finally {
                        try {
                            if (rs != null) rs.close();
                            if (pstmt != null) pstmt.close();
                        } catch (SQLException e1) {
                            e1.printStackTrace();
                        }
                    }
			}
		});
        
        panel.add(queryAProductInfoLabel);
        panel.add(queryAProductInfoField);
        panel.add(new JLabel());
        panel.add(queryAProductInfoButton);
        
        JButton queryProductInfoButton = new JButton("查询全部商品信息");
        
        queryProductInfoButton.addActionListener(new ActionListener() {
			
        	public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				String sql = "select commodityID,commodityName,commodityPrice,commodityCost,commodityRamin,supplierName "
						+ "from supplier,commodity where supplierID = supplier_supplierID order by commodityID";
				Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();
                    pstmt = connection.prepareStatement(sql);
                    rs = pstmt.executeQuery();
                    StringBuilder result = new StringBuilder();
                    while(rs.next()) {
                    	int ID = rs.getInt("commodityID");
                    	String name = rs.getString("commodityName");
                    	float price = rs.getFloat("commodityPrice");
                    	float cost = rs.getFloat("commodityCost");
                    	int ramin = rs.getInt("commodityRamin");
                    	String supplier = rs.getString("supplierName");
                    	
                    	result.append("编号：").append(ID).append("  名称:").append(name).append("  价格：").append(price+"元")
                    		  .append("  成本：").append(cost+"元").append("  库存：").append(ramin+"件")
                    		  .append("  供应商：").append(supplier).append("\n");
                    }
                    JTextArea resultArea = new JTextArea(result.toString());
                    resultArea.setFont(new Font("Monospaced", Font.PLAIN, 12));
                    resultArea.setLineWrap(true);
                    resultArea.setWrapStyleWord(true);
                    JScrollPane scrollPane = new JScrollPane(resultArea);
                    scrollPane.setPreferredSize(new Dimension(1000, 400)); // 设置滚动窗格的首选大小
                    JOptionPane.showMessageDialog(frame, scrollPane, "查询结果", JOptionPane.INFORMATION_MESSAGE);
                }
                   	catch (SQLException e1) {
                        e1.printStackTrace();
                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                    } finally {
                        try {
                            if (rs != null) rs.close();
                            if (pstmt != null) pstmt.close();
                        } catch (SQLException e1) {
                            e1.printStackTrace();
                        }
                    }
			}
		});
        
        panel.add(new JLabel()); // 空白占位符
        panel.add(queryProductInfoButton);

        // 查询供货商信息部分
        JButton querySupplierInfoButton = new JButton("查询全部供货商信息");
        
        querySupplierInfoButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				String sql = "select * from supplier";
				Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();
                    pstmt = connection.prepareStatement(sql);
                    rs = pstmt.executeQuery();
                    StringBuilder result = new StringBuilder();
                    while(rs.next()) {
                    	int ID = rs.getInt("supplierID");
                    	String name = rs.getString("supplierName");
                    	String phone = rs.getString("supplierPhone");
                    	String number = rs.getString("supplierNum");
                    	
                    	result.append("编号：").append(ID).append("  名称；").append(name).append("  电话：").append(phone).append("  营业执照编号：")
                    		  .append(number).append("\n");
                    }
                    JTextArea resultArea = new JTextArea(result.toString());
                    resultArea.setFont(new Font("Monospaced", Font.PLAIN, 12));
                    resultArea.setLineWrap(true);
                    resultArea.setWrapStyleWord(true);
                    JScrollPane scrollPane = new JScrollPane(resultArea);
                    scrollPane.setPreferredSize(new Dimension(1000, 400)); // 设置滚动窗格的首选大小
                    JOptionPane.showMessageDialog(frame, scrollPane, "查询结果", JOptionPane.INFORMATION_MESSAGE);
                }
                    catch (SQLException e1) {
                        e1.printStackTrace();
                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                    } finally {
                        try {
                            if (rs != null) rs.close();
                            if (pstmt != null) pstmt.close();
                        } catch (SQLException e1) {
                            e1.printStackTrace();
                        }
                    }
			}
		});
        
        panel.add(new JLabel()); // 空白占位符
        panel.add(querySupplierInfoButton);
        
        JLabel addProductIDLabel = new JLabel("请输入补货的商品编号：");
        JTextField addProductIDField = new JTextField();
        JLabel addProductNumLabel = new JLabel("请输入补货的商品数量：");
        JTextField addProductNumField = new JTextField();
        JButton addProductButton = new JButton("补货");
        
        addProductButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				if(!isValidEmployeeNum(addProductIDField.getText()) || !isValidEmployeeNum(addProductNumField.getText())) {
					JOptionPane.showMessageDialog(null, "商品号和数量只能是整数", "错误", JOptionPane.ERROR_MESSAGE);
					return;
				}
				Integer id = Integer.parseInt(addProductIDField.getText());
				Integer num = Integer.parseInt(addProductNumField.getText());
				String sql = "update commodity set commodityRamin = commodityRamin + ? where commodityID = ?";
				
				Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();
                    pstmt = connection.prepareStatement(sql);
                    pstmt.setInt(1, num);
                    pstmt.setInt(2, id);
                    int cout = pstmt.executeUpdate();
                    JOptionPane.showMessageDialog(frame, "已完成补货");
                }
                    catch (SQLException e1) {
                        e1.printStackTrace();
                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                    } finally {
                        try {
                            if (rs != null) rs.close();
                            if (pstmt != null) pstmt.close();
                        } catch (SQLException e1) {
                            e1.printStackTrace();
                        }
                    }
			}
		});
        
        panel.add(addProductIDLabel);
        panel.add(addProductIDField);
        panel.add(addProductNumLabel);
        panel.add(addProductNumField);
        panel.add(new JLabel());
        panel.add(addProductButton);
        
        JLabel deleteSupplierLabel = new JLabel("请输入解约供货商编号：");
        JTextField deleteSupplierField = new JTextField();
        JButton deleteSupplierButton = new JButton("点击解约");
        
        deleteSupplierButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				if(!isValidEmployeeNum(deleteSupplierField.getText())) {
					JOptionPane.showMessageDialog(null, "供应商编号只能是整数", "错误", JOptionPane.ERROR_MESSAGE);
					return;
				}
				String sql1 = "select commodityRamin from commodity,supplier where supplierID = supplier_supplierID and supplierID = ?";
				String sql2 = "delete from supplier where supplierID = ?";
				String sql3 = "select * from supplier where supplierID =?";
				Integer id = Integer.parseInt(deleteSupplierField.getText());
				Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();
                    pstmt = connection.prepareStatement(sql3);
                    pstmt.setInt(1, id);
                    rs = pstmt.executeQuery();
                    
                    if(!rs.next()) {
                    	JOptionPane.showMessageDialog(frame, "不存在对应的供应商");
                    	return;
                    }
                    rs.close();
                    
                    pstmt = connection.prepareStatement(sql1);
                    pstmt.setInt(1, id);
                    rs = pstmt.executeQuery();
                    
                    while(rs.next()) {
                    	Integer Ramin = rs.getInt("commodityRamin");
                    	if(Ramin != 0) {
                    		JOptionPane.showMessageDialog(null, "尚有货物没有卖完", "错误", JOptionPane.ERROR_MESSAGE);
                    		return;
                    	}
                    }
                    rs.close();
                    
                    pstmt = connection.prepareStatement(sql2);
                    pstmt.setInt(1, id);
                    
                    int cout = pstmt.executeUpdate();
                    JOptionPane.showMessageDialog(frame, "已完成解约，对应的货品信息也一并删除");
                }
                    catch (SQLException e1) {
                        e1.printStackTrace();
                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                    } finally {
                        try {
                            if (rs != null) rs.close();
                            if (pstmt != null) pstmt.close();
                        } catch (SQLException e1) {
                            e1.printStackTrace();
                        }
                    }
			}
		});
        
        panel.add(deleteSupplierLabel);
        panel.add(deleteSupplierField);
        panel.add(new JLabel());
        panel.add(deleteSupplierButton);
        
        JLabel addSupplierNameLabel = new JLabel("请输入供货商名称：");
        JTextField addSupplierNameField = new JTextField();
        JLabel addSupplierPhoneLabel = new JLabel("请输入供货商电话：");
        JTextField addSupplierPhoneField = new JTextField();
        JLabel addSupplierNumLabel = new JLabel("请输入供货商营业执照编号：");
        JTextField addSupplierNumField = new JTextField();
        JTextField showSupplierID = new JTextField("系统生成供货商编号");
        showSupplierID.setEditable(false);
        JButton addSupplierButton = new JButton("点击添加新供货商");
        
        addSupplierButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
				
				String name = addSupplierNameField.getText();
				String phone = addSupplierPhoneField.getText();
				String num = addSupplierNumField.getText();
				
				if(name.equals(null)||phone.equals(null)||num.equals(null)) {
					JOptionPane.showMessageDialog(frame, "信息不全");
					return;
				}
				
				if(!isValidPhone(phone)) {
					JOptionPane.showMessageDialog(frame, "电话不符合规范");
					return;
				}
				
				if(!isValidBusinessLicense(num)) {
					JOptionPane.showMessageDialog(frame, "营业执照不符合规范");
					return;
				}
				
				String sql1 = "insert into supplier (supplierName,supplierPhone,supplierNum) value (?,?,?)";
				String sql2 = "select supplierID from supplier where supplierName = ? order by supplierID desc";
				
				try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();
                    pstmt = connection.prepareStatement(sql1);
                    pstmt.setString(1, name);
                    pstmt.setString(2, phone);
                    pstmt.setString(3, num);
                    
                    int cout = pstmt.executeUpdate();
                    JOptionPane.showMessageDialog(frame, "插入成功");
                    
                    pstmt = connection.prepareStatement(sql2);
                    pstmt.setString(1, name);
                    
                    rs = pstmt.executeQuery();
                    if(rs.next()) {
                    	Integer id = rs.getInt("supplierID");
                    	showSupplierID.setText(id.toString());
                    	return;
                    }
                }
                    catch (SQLException e1) {
                        e1.printStackTrace();
                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                    } finally {
                        try {
                            if (rs != null) rs.close();
                            if (pstmt != null) pstmt.close();
                        } catch (SQLException e1) {
                            e1.printStackTrace();
                        }
                    }
			}
		});
        
        panel.add(addSupplierNameLabel);
        panel.add(addSupplierNameField);
        panel.add(addSupplierPhoneLabel);
        panel.add(addSupplierPhoneField);
        panel.add(addSupplierNumLabel);
        panel.add(addSupplierNumField);
        panel.add(showSupplierID);
        panel.add(addSupplierButton);
        
        JLabel addProductNameLabel = new JLabel("请输入商品名称：");
        JTextField addProductNameField = new JTextField();
        JLabel addProductPriceLabel = new JLabel("请输入商品价格：");
        JTextField addProductPriceField = new JTextField();
        JLabel addProductCostLabel = new JLabel("请输入商品成本：");
        JTextField addProductCostField = new JTextField();
        JLabel addProductRaminLabel = new JLabel("请输入商品数量：");
        JTextField addProductRaminField = new JTextField();
        JLabel addSupplierIDLabel = new JLabel("请输入供货商编号：");
        JTextField addSupplierIDField = new JTextField();
        JTextField showProductID = new JTextField("系统生成商品编号");
        showProductID.setEditable(false);
        JButton addNewProductButton = new JButton("点击添加新商品");
        
        addNewProductButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
				
				String namestr = addProductNameField.getText();
				String pricestr = addProductPriceField.getText();
				String coststr = addProductCostField.getText();
				String raminstr = addProductRaminField.getText();
				String idstr = addSupplierIDField.getText();
				
				if(namestr.isEmpty()||pricestr.isEmpty()||coststr.isEmpty()||raminstr.isEmpty()||idstr.isEmpty()) {
					JOptionPane.showMessageDialog(frame, "信息不全");
					return;
				}
				
				if((!isValidInt(pricestr)&&!isValidFloat(pricestr)) || (!isValidInt(coststr)&&!isValidFloat(coststr))) {
					JOptionPane.showMessageDialog(frame, "售价和成本输入不符合要求");
					return;
				}
				
				if(!isValidInt(raminstr)) {
					JOptionPane.showMessageDialog(frame, "数量只能是整数");
					return;
				}
				
				if(!isValidInt(idstr)) {
					JOptionPane.showMessageDialog(frame, "供货商编号只能是整数");
					return;
				}
				
				Float price = Float.parseFloat(pricestr);
				Float cost = Float.parseFloat(coststr);
				Integer ramin = Integer.parseInt(raminstr);
				Integer id = Integer.parseInt(idstr);
				
				String sql3 = "select * from supplier where supplierID = ?";
				try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();
                    pstmt = connection.prepareStatement(sql3);
                    pstmt.setInt(1, id);
                    
                    rs = pstmt.executeQuery();
                    if(!rs.next()) {
                    	JOptionPane.showMessageDialog(frame, "供货商不存在");
                    	return;
                    }
                    rs.close();
                }
                    catch (SQLException e1) {
                        e1.printStackTrace();
                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                    } finally {
                        try {
                            if (rs != null) rs.close();
                            if (pstmt != null) pstmt.close();
                        } catch (SQLException e1) {
                            e1.printStackTrace();
                        }
                    }
				
				String sql1 = "insert into commodity (commodityName,commodityPrice,commodityCost,commodityRamin,supplier_supplierID)"
						+ " value(?,?,?,?,?)";
				String sql2 = "select commodityID from commodity where commodityName = ? order by commodityID desc";
				
				try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();
                    pstmt = connection.prepareStatement(sql1);
                    pstmt.setString(1, namestr);
                    pstmt.setFloat(2, price);
                    pstmt.setFloat(3, cost);
                    pstmt.setInt(4,ramin);
                    pstmt.setInt(5, id);
                    
                    int cout = pstmt.executeUpdate();
                    JOptionPane.showMessageDialog(frame, "插入成功");
                    
                    pstmt = connection.prepareStatement(sql2);
                    pstmt.setString(1, namestr);
                    
                    rs = pstmt.executeQuery();
                    if(rs.next()) {
                    	Integer ID = rs.getInt("commodityID");
                    	showProductID.setText(ID.toString());
                    	return;
                    }
                }
                    catch (SQLException e1) {
                        e1.printStackTrace();
                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                    } finally {
                        try {
                            if (rs != null) rs.close();
                            if (pstmt != null) pstmt.close();
                        } catch (SQLException e1) {
                            e1.printStackTrace();
                        }
                    }
			}
		});
        
        panel.add(addProductNameLabel);
        panel.add(addProductNameField);
        panel.add(addProductPriceLabel);
        panel.add(addProductPriceField);
        panel.add(addProductCostLabel);
        panel.add(addProductCostField);
        panel.add(addProductRaminLabel);
        panel.add(addProductRaminField);
        panel.add(addSupplierIDLabel);
        panel.add(addSupplierIDField);
        panel.add(showProductID);
        panel.add(addNewProductButton);

        // 添加面板到框架
        frame.add(panel, BorderLayout.CENTER);

        // 显示窗口
        frame.setResizable(false);
        frame.setLocationRelativeTo(null);
        frame.setVisible(true);
    }
	public static boolean isValidFloat(String input) {
        return Pattern.matches("^[+-]?((\\d+(\\.\\d*)?)|(\\.\\d+))$", input);
    }
	private boolean isValidName(String name) {
        return Pattern.matches("[\\u4e00-\\u9fa5a-zA-Z]+", name);
    }

	private boolean isValidIdCard(String idCard) {
	    return Pattern.matches("(^\\d{15}$)|(^\\d{17}[0-9Xx]$)", idCard);
	}

    private boolean isValidPhone(String phone) {
        return Pattern.matches("[0-9#*]+", phone);
    }

    private boolean isValidInt(String salary) {
        return Pattern.matches("\\d+", salary);
    }

    private boolean isValidPassword(String password) {
        return Pattern.matches("[a-zA-Z0-9]{1,11}", password);
    }
    
    private static boolean isValidEmployeeNum(String str) {
        if (str == null || str.isEmpty()) {
            return false;
        }
        return Pattern.matches("\\d+", str);
    }
    
    private boolean isValidBusinessLicense(String licenseNumber) {
        return Pattern.matches("^[0-9A-Z]{18}$", licenseNumber);
    }

    private boolean isValidOffice(String office) {
        String sql = "select * from office where officeName = ?";
        Connection connection = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            // 获取数据库连接
            connection = LinkDateBase.getConnection();

            // SQL
            pstmt = connection.prepareStatement(sql);
            pstmt.setString(1, office);

            // 执行查询
            rs = pstmt.executeQuery();

            // 显示结果
            if(rs.next()) {
            	return true;
            }
            else {
            	return false;
            }
        } catch (SQLException e1) {
            e1.printStackTrace();
            JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
            return false;
        } finally {
            try {
                if (rs != null) rs.close();
                if (pstmt != null) pstmt.close();
            } catch (SQLException e1) {
                e1.printStackTrace();
            }
        }
    }

    private int generateUniqueEmployeeID(JFrame frame,String name, String idCard, String phone, Integer salary, String password1) {
        String sql1 = "select staffID from staff where staffName = ? and staffIdentNum = ? and staffPhone = ? and staffWage = ? and staffPassword = ? order by staffID desc";
        Connection connection = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            // 获取数据库连接
            connection = LinkDateBase.getConnection();

            // SQL
            pstmt = connection.prepareStatement(sql1);
            pstmt.setString(1, name);
            pstmt.setString(2, idCard);
            pstmt.setString(3, phone);
            pstmt.setInt(4, salary);
            pstmt.setString(5, password1);

            // 执行查询
            rs = pstmt.executeQuery();

            // 显示结果
            if(rs.next()) {
            	return rs.getInt("staffID");
            }
        } catch (SQLException e1) {
            e1.printStackTrace();
            JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
            return 0;
        } finally {
            try {
                if (rs != null) rs.close();
                if (pstmt != null) pstmt.close();
            } catch (SQLException e1) {
                e1.printStackTrace();
            }
        }
		return 0;
    }
}
