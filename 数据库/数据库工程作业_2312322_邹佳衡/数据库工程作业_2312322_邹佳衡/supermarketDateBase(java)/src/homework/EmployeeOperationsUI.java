package homework;

import java.awt.*;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

import javax.swing.*;

public class EmployeeOperationsUI {
	public EmployeeOperationsUI() {        
        // 创建主窗口
        JFrame frame = new JFrame("员工数据库控制界面");
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setSize(500, 1000); // 增加窗口高度以适应新控件
        frame.setLayout(new BorderLayout());

        // 创建面板
        JPanel panel = new JPanel();
        panel.setLayout(new GridLayout(25, 2, 10, 10)); // 设置网格布局

        // 设置边距
        panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));
        
        // 记录交易部分
        JLabel productCodeLabel = new JLabel("请输入商品编号: ");
        JTextField productCodeField = new JTextField();
        panel.add(productCodeLabel);
        panel.add(productCodeField);

        JLabel customerIdLabel = new JLabel("请输入顾客ID: ");
        JTextField customerIdField = new JTextField();
        panel.add(customerIdLabel);
        panel.add(customerIdField);
        
        JLabel commodityNumLabel = new JLabel("请输入商品数量：");
        JTextField commodityNumField = new JTextField();
        panel.add(commodityNumLabel);
        panel.add(commodityNumField);

        JButton recordTransactionButton = new JButton("记录交易");
        panel.add(new JLabel()); // 空白占位符
        
        recordTransactionButton.addActionListener(new ActionListener() {
			
        	public void actionPerformed(ActionEvent e) {
				if (validateFields(productCodeField, customerIdField, commodityNumField)) {
					Connection connection = null;
                    PreparedStatement pstmt = null;
                    ResultSet rs = null;
					// 获取当前时间
			        LocalDateTime now = LocalDateTime.now();
			        
			        // 定义日期时间格式
			        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
			        
			        // 格式化当前时间为指定格式的字符串
			        String formattedDateTime = now.format(formatter);
			        int commodityID = Integer.parseInt(productCodeField.getText());
			        int customID = Integer.parseInt(customerIdField.getText());
			        int commodityNum = Integer.parseInt(commodityNumField.getText());
			        
			        String sql4 = "select * from commodity where commodityID = ?";
			        String sql5 = "select * from custom where customID = ?";
			        
			        
			        
			        String sql1 = "select commodityPrice, commodityRamin from commodity where commodityID = ?";
			        
                    float commodityPrice = 0;
                    int commodityRamin = 0;
                    try {
                        // 获取数据库连接
                        connection = LinkDateBase.getConnection();
                        
                        pstmt = connection.prepareStatement(sql4);
                        pstmt.setInt(1,commodityID);
                        rs = pstmt.executeQuery();
                        
                        if(!rs.next()) {
                        	JOptionPane.showMessageDialog(frame, "商品不存在");
                        	return;
                        }
                        
                        rs.close();
                        
                        pstmt = connection.prepareStatement(sql5);
                        pstmt.setInt(1, customID);
                        rs = pstmt.executeQuery();
                        
                        if(!rs.next()) {
                        	JOptionPane.showMessageDialog(frame, "用户名不存在");
                        	return;
                        }

                        // SQL
                        pstmt = connection.prepareStatement(sql1);
                        pstmt.setInt(1, commodityID);

                        // 执行查询
                        rs = pstmt.executeQuery();

                        // 显示结果
                        if(rs.next()) {
                        	commodityPrice = rs.getFloat("commodityPrice");
                        	commodityRamin = rs.getInt("commodityRamin");
                        }
                    } catch (SQLException e1) {
                        e1.printStackTrace();
                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                        return;
                    } finally {
                        try {
                            if (rs != null) rs.close();
                            if (pstmt != null) pstmt.close();
                        } catch (SQLException e1) {
                            e1.printStackTrace();
                        }
                    }
                    
                    if (commodityRamin < commodityNum) {
                    	JOptionPane.showMessageDialog(frame, "库存不足", "错误", JOptionPane.ERROR_MESSAGE);
                    	return;
                    }
                    
                    float totalPrice = commodityPrice * commodityNum;
                    
                    String sql2 = "insert into trade (custom_customID, commodity_commodityID, tradeTime, commodityNum, sumPrice)"
                    		+ " values (?, ?, ?, ?, ?)";
                    try {
                        // SQL
                        pstmt = connection.prepareStatement(sql2);
                        pstmt.setInt(1, customID);
                        pstmt.setInt(2, commodityID);
                        pstmt.setString(3, formattedDateTime);
                        pstmt.setInt(4, commodityNum);
                        pstmt.setFloat(5, totalPrice);

                        // 执行查询
                        int result = pstmt.executeUpdate();
                        
                        if (result > 0) {
                        	// 更新商品库存
                        	String sql3 = "update commodity set commodityRamin = commodityRamin - ? where commodityID = ?";
                        	pstmt = connection.prepareStatement(sql3);
                        	pstmt.setInt(1, commodityNum);
                        	pstmt.setInt(2, commodityID);
                        	pstmt.executeUpdate();
                        }
                    } catch (SQLException e1) {
                        e1.printStackTrace();
                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                    } finally {
                        try {
                            if (pstmt != null) pstmt.close();
                            if (connection != null) connection.close();
                        } catch (SQLException e1) {
                            e1.printStackTrace();
                        }
                    }
                    
                    //交易满100元，加一点积分
                    int addPoint = (int) (totalPrice / 100);
                    String sql3 = "update custom set customPoint = customPoint + ? where customID = ?";
                    try {
                        // SQL
                    	connection = LinkDateBase.getConnection();
                        pstmt = connection.prepareStatement(sql3);
                        pstmt.setInt(1, addPoint);
                        pstmt.setInt(2, customID);
                        // 执行查询
                        int result = pstmt.executeUpdate();
                    } catch (SQLException e1) {
                        e1.printStackTrace();
                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                    } finally {
                        try {
                            if (pstmt != null) pstmt.close();
                            if (connection != null) connection.close();
                        } catch (SQLException e1) {
                            e1.printStackTrace();
                        }
                    }
                    
				} 
				else {
					JOptionPane.showMessageDialog(frame, "所有字段必须填写且只能包含数字", "输入错误", JOptionPane.ERROR_MESSAGE);
				}
			}
		});
        
        panel.add(recordTransactionButton);

        // 查询交易记录部分
        JLabel yearLabel = new JLabel("请输入年份 (yyyy): ");
        JTextField yearField = new JTextField();
        panel.add(yearLabel);
        panel.add(yearField);

        JLabel monthLabel = new JLabel("请输入月份 (MM): ");
        JTextField monthField = new JTextField();
        panel.add(monthLabel);
        panel.add(monthField);

        JLabel dayLabel = new JLabel("请输入日期 (dd): ");
        JTextField dayField = new JTextField();
        panel.add(dayLabel);
        panel.add(dayField);

        JLabel personIdLabel = new JLabel("请输入人员ID: ");
        JTextField personIdField = new JTextField();
        panel.add(personIdLabel);
        panel.add(personIdField);

        JLabel productNameLabel = new JLabel("请输入商品关键词: ");
        JTextField productNameField = new JTextField();
        panel.add(productNameLabel);
        panel.add(productNameField);

        JButton queryProductTransactionsButton = new JButton("查询某交易");
        panel.add(new JLabel()); // 空白占位符
        panel.add(queryProductTransactionsButton);
        
        queryProductTransactionsButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				String yearStr = yearField.getText(), monthStr = monthField.getText(), dayStr = dayField.getText();
				String customIDStr =personIdField.getText();
				String commodityNameStr =productNameField.getText();
				
				String sql = "select customName,commodityName,tradeTime,commodityNum,sumPrice from custom,commodity,trade"
						+ " where customID=custom_customID and commodityID=commodity_commodityID";
				String startDay = null;
				String endDay = null;
				Integer customID = null;
				if(yearStr.isEmpty()&&customIDStr.isEmpty()&&commodityNameStr.isEmpty()) {
					return;
				}
            	if(!yearStr.isEmpty()) {
            		String year = yearStr;
            		String month =monthStr.isEmpty()?"01":monthStr;
            		String day =dayStr.isEmpty()?"01":dayStr;
            		String totalDay = null;
            		month = month.length()==1?"0"+month:month;
            		day = day.length()==1?"0"+day:day;
            		Integer yearInt =Integer.parseInt(yearStr);
            		Integer monthInt = Integer.parseInt(month);
            	
            		switch(monthInt){
            		case 1: case 3: case 5: case 7: case 8: case 10: case 12:
            			totalDay = "31";
            			break;
            		case 4: case 6: case 9: case 11:
            			totalDay = "30";
            			break;
            		case 2:
            			if ((yearInt % 4 == 0 && yearInt % 100 != 0) || (yearInt % 400 == 0)) {
            				totalDay = "29"; // 闰年
            			} else {
            				totalDay = "28"; // 平年
            			}
            			break;
            		default:
            			break;
            		}

            		String base = year+"-"+month+"-"+day;
            		startDay = base+" "+"00:00:00";
            		endDay = !dayStr.isEmpty()?base+" "+"23:59:59":
            			!monthStr.isEmpty()?year+"-"+month+"-"+totalDay+" "+"23:59:59":
            				year+"-12-31"+" "+"23:59:59";
            		
            		sql+=" and (tradeTime between ? and ?)";
            	}
            	if(!customIDStr.isEmpty()) {
            		customID = Integer.parseInt(customIDStr);
            		sql+=" and customID = ?";
            	}
            	if(!commodityNameStr.isEmpty()) {
            		sql+=" and commodityName like ?";
            	}
            	sql+=" order by tradeTime desc;";
//            	System.out.println(sql);
            	Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql);
                    
                    int parameterIndex = 1;
                    if(startDay != null && endDay != null) {
                    	pstmt.setString(parameterIndex++, startDay);
                    	pstmt.setString(parameterIndex++, endDay);
                    }
                    if(customID != null) {
                    	pstmt.setInt(parameterIndex++, customID);
                    }
                    if(!commodityNameStr.isEmpty()) {
                    	pstmt.setString(parameterIndex++, "%" + commodityNameStr + "%");
                    }

                    // 执行查询
                    rs = pstmt.executeQuery();

                    // 显示结果
                    StringBuilder result = new StringBuilder();
                    while(rs.next()) {
                    	String customName = rs.getString("customName");
                    	String commodityName = rs.getString("commodityName");
                        String tradeTime = rs.getTimestamp("tradeTime").toString();
                        int commodityNum = rs.getInt("commodityNum");
                        int sumPrice = rs.getInt("sumPrice");

                        result.append("姓名：").append(customName).append("  ").append("商品：").append(commodityName)
                        	  .append("  ").append(commodityNum).append("件  ").append(sumPrice).append("元  ")
                        	  .append("时间：").append(tradeTime).append("\n");
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
                    return;
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

        JButton queryAllTransactionsButton = new JButton("查询全部交易");
        panel.add(new JLabel()); // 空白占位符
        panel.add(queryAllTransactionsButton);
        
        queryAllTransactionsButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				String sql = "select customName,commodityName,tradeTime,commodityNum,sumPrice from trade,custom,commodity where"
						+ " commodity_commodityID = commodityID"+" and custom_customID = customID order by tradeTime desc;";
				
				Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                System.out.println(sql);
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql);

                    // 执行查询
                    rs = pstmt.executeQuery();

                    // 显示结果
                    StringBuilder result = new StringBuilder();
                    while(rs.next()) {
                    	String customName = rs.getString("customName");
                    	String commodityName = rs.getString("commodityName");
                        String tradeTime = rs.getTimestamp("tradeTime").toString();
                        int commodityNum = rs.getInt("commodityNum");
                        int sumPrice = rs.getInt("sumPrice");

                        result.append("姓名：").append(customName).append("  ").append("商品：").append(commodityName)
                        	  .append("  ").append(commodityNum).append("件  ").append(sumPrice).append("元  ")
                        	  .append("时间：").append(tradeTime).append("\n");
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
                        if (connection != null) connection.close();
                    } catch (SQLException e1) {
                        e1.printStackTrace();
                    }
                }
			}
		});

        // 查询商品价格部分
        JLabel productPriceNameLabel = new JLabel("请输入商品编号: ");
        JTextField productPriceNameField = new JTextField();
        panel.add(productPriceNameLabel);
        panel.add(productPriceNameField);

        JButton queryProductPriceButton = new JButton("查询商品价格");
        panel.add(new JLabel()); // 空白占位符
        panel.add(queryProductPriceButton);
        
        JLabel showProductPrice = new JLabel("商品价格：");
        JTextField ProductPriceField = new JTextField();
        ProductPriceField.setEditable(false);
        panel.add(showProductPrice);
        panel.add(ProductPriceField);
        
        queryProductPriceButton.addActionListener(new ActionListener() {
			
        	@Override
			public void actionPerformed(ActionEvent e) {
				// 检查输入是否为数字
        		Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
				if (!validateFields(productPriceNameField)) {
					JOptionPane.showMessageDialog(frame, "商品编号必须是数字", "输入错误", JOptionPane.ERROR_MESSAGE);
					return;
				}

				int commodityID = Integer.parseInt(productPriceNameField.getText());
				
				String sql = "select commodityPrice from commodity where commodityID = ?";
                Float commodityPrice = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql);
                    pstmt.setInt(1, commodityID);

                    // 执行查询
                    rs = pstmt.executeQuery();

                    // 显示结果
                    if (rs.next()) {
                    	commodityPrice = rs.getFloat("commodityPrice");
                    	ProductPriceField.setText(commodityPrice.toString()+"元");
                    }else {
                    	JOptionPane.showMessageDialog(frame, "不存在该商品");
                    	return;
                    }
                } catch (SQLException e1) {
                    e1.printStackTrace();
                    JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                } finally {
                    try {
                        if (rs != null) rs.close();
                        if (pstmt != null) pstmt.close();
                        if (connection != null) connection.close();
                    } catch (SQLException e1) {
                        e1.printStackTrace();
                    }
                }

                if (commodityPrice != null) {
                	ProductPriceField.setText(String.valueOf(commodityPrice));
                } else {
                	JOptionPane.showMessageDialog(frame, "未找到该商品编号的商品", "错误", JOptionPane.ERROR_MESSAGE);
                }
			}
		});

        // 查询用户剩余积分部分
        JLabel usernameLabel = new JLabel("请输入用户名: ");
        JTextField usernameField = new JTextField();
        panel.add(usernameLabel);
        panel.add(usernameField);

        JLabel passwordLabel = new JLabel("请输入密码: ");
        JPasswordField passwordField = new JPasswordField();
        panel.add(passwordLabel);
        panel.add(passwordField);

        JButton queryUserPointsButton = new JButton("查询用户剩余积分");
        panel.add(new JLabel()); // 空白占位符
        panel.add(queryUserPointsButton);
        
        JLabel showUserPoint = new JLabel("用户剩余积分：");
        JTextField userPointField = new JTextField();
        userPointField.setEditable(false);
        panel.add(showUserPoint);
        panel.add(userPointField);
        
        queryUserPointsButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				int ID = 0;
                try {
                    String username = usernameField.getText();
                    ID = Integer.parseInt(username);
                } catch (NumberFormatException e1) {
                    JOptionPane.showMessageDialog(frame, "用户名只能是数字!", "错误", JOptionPane.ERROR_MESSAGE);
                    return; // 如果格式错误，停止执行
                }
                char[] passwordChars = passwordField.getPassword();
                String password = new String(passwordChars);

                // 验证逻辑
                boolean isPass = authenticate(ID, password);
                if (isPass) {
                    String sql = "select customPoint from custom where customID = ?;";
                    Connection connection = null;
                    PreparedStatement pstmt = null;
                    ResultSet rs = null;
                    Integer customPoint = 0;
                    try {
                        // 获取数据库连接
                        connection = LinkDateBase.getConnection();

                        // SQL
                        pstmt = connection.prepareStatement(sql);
                        pstmt.setInt(1, ID);

                        // 执行查询
                        rs = pstmt.executeQuery();

                        // 显示结果
                        if(rs.next()) {
                        	customPoint = rs.getInt("customPoint");
                        	userPointField.setText(customPoint.toString());
                        }
                    } catch (SQLException e1) {
                        e1.printStackTrace();
                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
                    } finally {
                        try {
                            if (rs != null) rs.close();
                            if (pstmt != null) pstmt.close();
                            if (connection != null) connection.close();
                        } catch (SQLException e1) {
                            e1.printStackTrace();
                        }
                    }
                } else {
                    JOptionPane.showMessageDialog(frame, "用户名或密码错误！", "错误", JOptionPane.ERROR_MESSAGE);
                }
			}
		});
        
        JLabel exchangeGiftLabel = new JLabel("请输入礼品ID：");
        JTextField exchangeGiftField = new JTextField();
        JLabel exchagneUserLabel = new JLabel("请输入用户ID：");
        JTextField exchangeUserField = new JTextField();
        JLabel exchangePasswordLabel = new JLabel("请输入用户密码：");
        JTextField exchangePasswordField = new JTextField();
        JLabel exchangeGiftNumLabel = new JLabel("请输入兑换数量：");
        JTextField exchangeGiftNumField = new JTextField();
        
        JButton exchangeGift = new JButton("兑换礼品");
        
        exchangeGift.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
		        Integer customID = Integer.parseInt(exchangeUserField.getText());
		        String customPassword = exchangePasswordField.getText();
		        if(authenticate(customID, customPassword)) {
					if (validateFields(exchangeGiftField, exchangeUserField, exchangeGiftNumField)) {
						// 获取当前时间
				        LocalDateTime now = LocalDateTime.now();
				        
				        // 定义日期时间格式
				        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
				        
				        // 格式化当前时间为指定格式的字符串
				        String formattedDateTime = now.format(formatter);
				        Integer giftID = Integer.parseInt(exchangeGiftField.getText());
				        Integer giftNum = Integer.parseInt(exchangeGiftNumField.getText());
				        
				        //获取礼品的剩余数量和兑换积分
				        String sql1 = "select giftPoint, giftNum from gift where giftID = ?;";
				        Connection connection = null;
	                    PreparedStatement pstmt = null;
	                    ResultSet rs = null;
	                    Integer giftPoint = 0;
	                    Integer giftRamin = 0;
	                    try {
	                        // 获取数据库连接
	                        connection = LinkDateBase.getConnection();
	
	                        // SQL
	                        pstmt = connection.prepareStatement(sql1);
	                        pstmt.setInt(1, giftID);
	
	                        // 执行查询
	                        rs = pstmt.executeQuery();
	
	                        // 显示结果
	                        if(rs.next()) {
	                        	giftPoint = rs.getInt("giftpoint");
	                        	giftRamin = rs.getInt("giftNum");
	                        }
	                    } catch (SQLException e1) {
	                        e1.printStackTrace();
	                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
	                        return;
	                    } finally {
	                        try {
	                            if (rs != null) rs.close();
	                            if (pstmt != null) pstmt.close();
	                        } catch (SQLException e1) {
	                            e1.printStackTrace();
	                        }
	                    }
	                    
	                    //获取顾客的剩余积分
	                    int customPoint = 0;
	                    String sql2 = "select customPoint from custom where customID = ?;";
	                    try {
	                        // 获取数据库连接
	                        connection = LinkDateBase.getConnection();
	
	                        // SQL
	                        pstmt = connection.prepareStatement(sql2);
	                        pstmt.setInt(1, customID);
	
	                        // 执行查询
	                        rs = pstmt.executeQuery();
	
	                        // 显示结果
	                        if(rs.next()) {
	                        	customPoint = rs.getInt("customPoint");
	                        }
	                    } catch (SQLException e1) {
	                        e1.printStackTrace();
	                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
	                        return;
	                    } finally {
	                        try {
	                            if (rs != null) rs.close();
	                            if (pstmt != null) pstmt.close();
	                        } catch (SQLException e1) {
	                            e1.printStackTrace();
	                        }
	                    }
	                    
	                    if (giftPoint*giftNum > customPoint) {
	                    	JOptionPane.showMessageDialog(frame, "积分不足", "错误", JOptionPane.ERROR_MESSAGE);
	                    	return;
	                    }
	                    
	                    if (giftRamin < giftNum) {
	                    	JOptionPane.showMessageDialog(frame, "库存不足，还剩"+giftRamin.toString()+"份", "错误", JOptionPane.ERROR_MESSAGE);
	                    	return;
	                    }
	                    
	                    Integer totalPoint = giftPoint * giftNum;
	                    
	                    //更新兑换记录
	                    String sql3 = "insert into exchangegift (custom_customID, gift_giftID, exchangeTime, exchangeNum)"
	                    		+ " values (?, ?, ?, ?)";
	                    try {
	                    	// 获取数据库连接
	                        connection = LinkDateBase.getConnection();
	
	                        // SQL
	                        pstmt = connection.prepareStatement(sql3);
	                        pstmt.setInt(1, customID);
	                        pstmt.setInt(2, giftID);
	                        pstmt.setString(3, formattedDateTime);
	                        pstmt.setInt(4, giftNum);
	
	                        // 执行查询
	                        int result = pstmt.executeUpdate();
	                        
	                        if (result > 0) {
	                        	// 更新商品库存
	                        	String sql4 = "update gift set giftNum = giftNum - ? where giftID = ?";
	                        	pstmt = connection.prepareStatement(sql4);
	                        	pstmt.setInt(1, giftNum);
	                        	pstmt.setInt(2, giftID);
	                        	pstmt.executeUpdate();
	                        }
	                    } catch (SQLException e1) {
	                        e1.printStackTrace();
	                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
	                    } finally {
	                        try {
	                            if (pstmt != null) pstmt.close();
	                            if (connection != null) connection.close();
	                        } catch (SQLException e1) {
	                            e1.printStackTrace();
	                        }
	                    }
	                    
	                    //更新顾客积分
	                    
	                    String sql5 = "update custom set customPoint = customPoint - ? where customID = ?";
	                    try {
	                    	// 获取数据库连接
	                        connection = LinkDateBase.getConnection();
	
	                    	pstmt = connection.prepareStatement(sql5);
	                    	pstmt.setInt(1, totalPoint);
	                    	pstmt.setInt(2, customID);
	                    	pstmt.executeUpdate();
	                    } catch (SQLException e1) {
	                        e1.printStackTrace();
	                        JOptionPane.showMessageDialog(null, "数据库错误: " + e1.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
	                    } finally {
	                        try {
	                            if (pstmt != null) pstmt.close();
	                            if (connection != null) connection.close();
	                        } catch (SQLException e1) {
	                            e1.printStackTrace();
	                        }
	                    }
					} 
					else {
						JOptionPane.showMessageDialog(frame, "所有字段必须填写且只能包含数字", "输入错误", JOptionPane.ERROR_MESSAGE);
						return;
					}
		        }
		        else {
		        	JOptionPane.showMessageDialog(frame, "用户名或密码错误", "错误", JOptionPane.ERROR_MESSAGE);
		        	return;
		        }
			}
		});
        
        panel.add(exchangeGiftLabel);
        panel.add(exchangeGiftField);
        panel.add(exchagneUserLabel);
        panel.add(exchangeUserField);
        panel.add(exchangePasswordLabel);
        panel.add(exchangePasswordField);
        panel.add(exchangeGiftNumLabel);
        panel.add(exchangeGiftNumField);
        panel.add(new JLabel());
        panel.add(exchangeGift);
        
        JLabel welcome =new JLabel("欢迎使用超市数据库控制系统。");

        // 添加面板到框架
        frame.add(panel, BorderLayout.CENTER);
        frame.add(welcome,BorderLayout.NORTH);

        // 显示窗口
        frame.setResizable(false);
        frame.setLocationRelativeTo(null);
        frame.setVisible(true);
    }
	
	private boolean validateFields(JTextField... fields) {
        for (JTextField field : fields) {
            if (field.getText().trim().isEmpty()) {
                return false;
            }
            try {
                Integer.parseInt(field.getText().trim());
            } catch (NumberFormatException e) {
                return false;
            }
        }
        return true;
    }
	
	private boolean authenticate(int userID, String password) {
        Connection connection = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            // 获取数据库连接
            connection = LinkDateBase.getConnection();

            // SQL 查询
            String sql = "select customPassword FROM custom where customID = ?";
            pstmt = connection.prepareStatement(sql);
            pstmt.setInt(1, userID);

            // 执行查询
            rs = pstmt.executeQuery();

            // 检查结果
            if (rs.next()) {
                String storedPassword = rs.getString("customPassword");
                return storedPassword.equals(password);
            }
        } catch (SQLException e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(null, "数据库错误: " + e.getMessage(), "错误", JOptionPane.ERROR_MESSAGE);
        } finally {
            try {
                if (rs != null) rs.close();
                if (pstmt != null) pstmt.close();
                if (connection != null) connection.close();
            } catch (SQLException e) {
                e.printStackTrace();
            }
        }
        return false;
    }
}