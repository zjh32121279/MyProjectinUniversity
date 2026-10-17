package homework;

import java.awt.BorderLayout;
import java.awt.Component;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.GridLayout;
import java.awt.Insets;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

import javax.swing.BorderFactory;
import javax.swing.Box;
import javax.swing.JButton;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.JViewport;
import javax.swing.SwingConstants;
import javax.swing.SwingUtilities;

public class UserOperationsUI {
	public UserOperationsUI() {		
		// TODO Auto-generated constructor stub
		// 创建主窗口
        JFrame frame = new JFrame("超市数据库数据查询");
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setSize(600, 525); // 增加窗口高度以适应新控件
        frame.setLayout(new BorderLayout());

        // 创建面板
        JPanel panel = new JPanel();
        panel.setLayout(new GridLayout(7, 2, 10, 10)); // 增加行数以适应新控件

        // 添加控件
        JLabel yearLabel = new JLabel("请输入年份 (yyyy): ");
        JTextField yearField = new JTextField();

        JLabel monthLabel = new JLabel("请输入月份 (m或mm): ");
        JTextField monthField = new JTextField();

        JLabel dayLabel = new JLabel("请输入日期 (d或dd): ");
        JTextField dayField = new JTextField();

        JButton queryDateButton = new JButton("查询某天/月/年交易");
        JButton queryAllPriceButton = new JButton("查询全部商品价格");
        JButton queryAllButton = new JButton("查询全部交易");

        JLabel productLabel = new JLabel("请输入商品关键词: ");
        JTextField productField = new JTextField();
        JButton queryProductPriceButton = new JButton("查询商品价格");
        
        JLabel pointLabel = new JLabel("用户剩余积分：");
        JTextField showUserPoint = new JTextField();
        showUserPoint.setEditable(false);
        JButton queryUserPointsButton = new JButton("查询用户积分");

        JLabel giftLabel = new JLabel("请输入礼品关键词: ");
        JTextField giftField = new JTextField();
        JButton queryGiftPointsButton = new JButton("查询礼品兑换积分");
        
        JLabel tips = new JLabel("查询月交易时，日期可以为空；查询年交易时，月份和日期可以为空。");
        JLabel welcome = new JLabel("尊敬的用户，欢迎使用超市数据库管理系统。");
        //添加监听器:
        queryDateButton.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                if (!isValidYear(yearField.getText()) || !isValidMonthAndDay(yearField.getText(), monthField.getText(), dayField.getText())) {
                    JOptionPane.showMessageDialog(frame, "请确保输入正确的年份（4位）、月份（1或2位）和日期（1或2位）。", "错误", JOptionPane.ERROR_MESSAGE);
                } else {
                    // 处理查询逻辑
                	String yearStr = yearField.getText(), monthStr = monthField.getText(), dayStr = dayField.getText();
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
                	String startDay = base+" "+"00:00:00";
                	String endDay = !dayStr.isEmpty()?base+" "+"23:59:59":
                					!monthStr.isEmpty()?year+"-"+month+"-"+totalDay+" "+"23:59:59":
                					year+"-12-31"+" "+"23:59:59";
                	
                	String sql = "select commodityName,tradeTime,commodityNum,sumPrice from trade,custom,commodity "
                			+ "where (tradeTime between '"+startDay+"' and '"+endDay+"') "
                					+ "and custom_customID = ?"+" and commodity_commodityID = commodityID"+" and custom_customID = customID"
                						+" ORDER BY tradeTime DESC;";
                	
                	Connection connection = null;
                    PreparedStatement pstmt = null;
                    ResultSet rs = null;
                    try {
                        // 获取数据库连接
                        connection = LinkDateBase.getConnection();

                        // SQL
                        pstmt = connection.prepareStatement(sql);
                        pstmt.setInt(1, UserLoginUI.userID);

                        // 执行查询
                        rs = pstmt.executeQuery();

                        // 检查结果
                        StringBuilder result = new StringBuilder();
                        while (rs.next()) {
                            String commodityName = rs.getString("commodityName");
                            String tradeTime = rs.getTimestamp("tradeTime").toString();
                            int commodityNum = rs.getInt("commodityNum");
                            int sumPrice = rs.getInt("sumPrice");

                            result.append(commodityName).append("  ").append(tradeTime).append("  数量：")
                                  .append(commodityNum).append("  总价：").append(sumPrice).append("\n");
                        }

                        // 显示结果
                        JTextArea resultArea = new JTextArea(result.toString());
                        resultArea.setFont(new Font("Monospaced", Font.PLAIN, 12));
                        resultArea.setLineWrap(true);
                        resultArea.setWrapStyleWord(true);
                        JScrollPane scrollPane = new JScrollPane(resultArea);
                        scrollPane.setPreferredSize(new Dimension(700, 400)); // 设置滚动窗格的首选大小
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
            }
        });
        
        queryAllButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				String sql = "SELECT commodityName, tradeTime, commodityNum, sumPrice FROM trade, custom, commodity"
						+" WHERE custom.customID = trade.custom_customID AND commodity.commodityID = trade.commodity_commodityID AND custom.customID = ?";
				Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
				try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql);
                    pstmt.setInt(1, UserLoginUI.userID);

                    // 执行查询
                    rs = pstmt.executeQuery();

                    // 检查结果
                    StringBuilder result = new StringBuilder();
                    while (rs.next()) {
                        String commodityName = rs.getString("commodityName");
                        String tradeTime = rs.getTimestamp("tradeTime").toString();
                        int commodityNum = rs.getInt("commodityNum");
                        int sumPrice = rs.getInt("sumPrice");

                        result.append(commodityName).append("  ").append(tradeTime).append("   数量：")
                              .append(commodityNum).append("  总价：").append(sumPrice).append("\n");
                    }

                    // 显示结果
                    JTextArea resultArea = new JTextArea(result.toString());
                    resultArea.setFont(new Font("Monospaced", Font.PLAIN, 12));
                    resultArea.setLineWrap(true);
                    resultArea.setWrapStyleWord(true);
                    JScrollPane scrollPane = new JScrollPane(resultArea);
                    scrollPane.setPreferredSize(new Dimension(700, 400)); // 设置滚动窗格的首选大小
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
        
        queryUserPointsButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				String sql = "select customPoint from custom where customID = ?;";
				Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
				try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql);
                    pstmt.setInt(1, UserLoginUI.userID);

                    // 执行查询
                    rs = pstmt.executeQuery();

                    // 检查结果
                    if (rs.next()) {
                        Integer point = rs.getInt("customPoint");
                        showUserPoint.setText(point.toString());
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
			}
		});
        
        queryProductPriceButton.addActionListener(new ActionListener() {

            @Override
            public void actionPerformed(ActionEvent e) {
                String keyword = productField.getText(); // 获取用户输入的商品关键词
                String sql = "select commodityName, commodityPrice, commodityRamin from commodity where commodityName like ?;";
                Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql);
                    pstmt.setString(1, "%" + keyword + "%"); // 使用通配符进行模糊匹配


                    // 执行查询
                    rs = pstmt.executeQuery();

                    // 检查结果
                    StringBuilder result = new StringBuilder();
                    while (rs.next()) {
                        String commodityName = rs.getString("commodityName");
                        float commodityPrice = rs.getFloat("commodityPrice");
                        int commodityRamin = rs.getInt("commodityRamin");

                        result.append(commodityName).append("  ").append(commodityPrice).append("元  剩余").append(commodityRamin).append("件\n");
                    }

                    // 显示结果
                    JTextArea resultArea = new JTextArea(result.toString());
                    resultArea.setFont(new Font("Monospaced", Font.PLAIN, 12));
                    resultArea.setLineWrap(true);
                    resultArea.setWrapStyleWord(true);
                    JScrollPane scrollPane = new JScrollPane(resultArea);
                    scrollPane.setPreferredSize(new Dimension(700, 400)); // 设置滚动窗格的首选大小
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
        
        queryAllPriceButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				String sql = "select commodityName, commodityPrice, commodityRamin from commodity;";
                Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql);

                    // 执行查询
                    rs = pstmt.executeQuery();

                    // 检查结果
                    StringBuilder result = new StringBuilder();
                    while (rs.next()) {
                        String commodityName = rs.getString("commodityName");
                        float commodityPrice = rs.getFloat("commodityPrice");
                        int commodityRamin = rs.getInt("commodityRamin");

                        result.append(commodityName).append("  ").append(commodityPrice).append("元  剩余").append(commodityRamin).append("件\n");
                    }

                    // 显示结果
                    JTextArea resultArea = new JTextArea(result.toString());
                    resultArea.setFont(new Font("Monospaced", Font.PLAIN, 12));
                    resultArea.setLineWrap(true);
                    resultArea.setWrapStyleWord(true);
                    JScrollPane scrollPane = new JScrollPane(resultArea);
                    scrollPane.setPreferredSize(new Dimension(700, 400)); // 设置滚动窗格的首选大小
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
        
        queryGiftPointsButton.addActionListener(new ActionListener() {
			
			@Override
			public void actionPerformed(ActionEvent e) {
				// TODO Auto-generated method stub
				String keyword = giftField.getText(); // 获取用户输入的商品关键词
                String sql = "select giftName, giftPoint, giftNum from gift where giftName like ?;";
                Connection connection = null;
                PreparedStatement pstmt = null;
                ResultSet rs = null;
                try {
                    // 获取数据库连接
                    connection = LinkDateBase.getConnection();

                    // SQL
                    pstmt = connection.prepareStatement(sql);
                    pstmt.setString(1, "%" + keyword + "%"); // 使用通配符进行模糊匹配


                    // 执行查询
                    rs = pstmt.executeQuery();

                    // 检查结果
                    StringBuilder result = new StringBuilder();
                    while (rs.next()) {
                        String commodityName = rs.getString("giftName");
                        int commodityPrice = rs.getInt("giftPoint");
                        int commodityRamin = rs.getInt("giftNum");

                        result.append(commodityName).append("  ").append(commodityPrice).append("积分  剩余").append(commodityRamin).append("份\n");
                    }

                    // 显示结果
                    JTextArea resultArea = new JTextArea(result.toString());
                    resultArea.setFont(new Font("Monospaced", Font.PLAIN, 12));
                    resultArea.setLineWrap(true);
                    resultArea.setWrapStyleWord(true);
                    JScrollPane scrollPane = new JScrollPane(resultArea);
                    scrollPane.setPreferredSize(new Dimension(700, 400)); // 设置滚动窗格的首选大小
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

        // 将控件添加到面板
        panel.add(yearLabel);
        panel.add(monthLabel);
        panel.add(dayLabel);
        
        panel.add(yearField);
        panel.add(monthField);
        panel.add(dayField);

        panel.add(queryDateButton);

        panel.add(queryAllPriceButton);
        panel.add(queryAllButton);

        panel.add(productLabel);
        panel.add(productField);
        panel.add(queryProductPriceButton);

        panel.add(pointLabel);
        panel.add(showUserPoint);
        panel.add(queryUserPointsButton);

        panel.add(giftLabel);
        panel.add(giftField);
        panel.add(queryGiftPointsButton);

        // 设置边距
        panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));
        
        // 添加面板到框架
        frame.add(panel, BorderLayout.CENTER);
        frame.add(welcome,BorderLayout.NORTH);
        frame.add(tips,BorderLayout.SOUTH);
        frame.setResizable(false);
        frame.setLocationRelativeTo(null);

        // 显示窗口
        frame.setVisible(true);
    }
	private boolean isValidYear(String text) {
        return text.matches("\\d{4}");
    }

    private boolean isValidMonthAndDay(String yearText, String monthText, String dayText) {
        if (monthText.isEmpty()) {
            return dayText.isEmpty(); // 如果月份为空，日期也必须为空
        }

        int year = Integer.parseInt(yearText);
        int month = Integer.parseInt(monthText);
        int maxDaysInMonth;

        switch (month) {
            case 1: case 3: case 5: case 7: case 8: case 10: case 12:
                maxDaysInMonth = 31;
                break;
            case 4: case 6: case 9: case 11:
                maxDaysInMonth = 30;
                break;
            case 2:
                if ((year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)) {
                    maxDaysInMonth = 29; // 闰年
                } else {
                    maxDaysInMonth = 28; // 平年
                }
                break;
            default:
                return false; // 无效的月份
        }

        if (dayText.isEmpty()) {
            return true; // 日期可以为空
        }

        int day = Integer.parseInt(dayText);
        return day >= 1 && day <= maxDaysInMonth;
    }
}
