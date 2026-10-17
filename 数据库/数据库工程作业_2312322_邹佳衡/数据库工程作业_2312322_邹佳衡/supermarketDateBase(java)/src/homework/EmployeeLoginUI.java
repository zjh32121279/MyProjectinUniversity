package homework;

import javax.swing.*;
import java.awt.*;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

public class EmployeeLoginUI{
	public static int userID;
	public EmployeeLoginUI() {
		// TODO Auto-generated constructor stub
		// 创建主窗口
        JFrame frame = new JFrame("员工登录");
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setSize(300, 200);
        frame.setLayout(new GridLayout(4, 1));

        // 添加欢迎信息
        JLabel welcomeLabel = new JLabel("员工登录", SwingConstants.CENTER);
        frame.add(welcomeLabel);

        // 用户名标签和文本框
        JPanel usernamePanel = new JPanel();
        usernamePanel.setLayout(new FlowLayout());
        JLabel usernameLabel = new JLabel("用户名:");
        JTextField usernameField = new JTextField(15);
        usernamePanel.add(usernameLabel);
        usernamePanel.add(usernameField);
        frame.add(usernamePanel);

        // 密码标签和文本框
        JPanel passwordPanel = new JPanel();
        passwordPanel.setLayout(new FlowLayout());
        JLabel passwordLabel = new JLabel("密码:");
        JPasswordField passwordField = new JPasswordField(15);
        passwordPanel.add(passwordLabel);
        passwordPanel.add(passwordField);
        frame.add(passwordPanel);

        // 按钮面板
        JPanel buttonPanel = new JPanel();
        buttonPanel.setLayout(new FlowLayout());

        JButton loginButton = new JButton("登录");
        loginButton.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                String username = usernameField.getText();
                int ID = 0;
                try {
                	ID = Integer.parseInt(username);
                	userID=ID;
                }catch(NumberFormatException e1) {
                	JOptionPane.showMessageDialog(frame, "用户名只能是数字!", "错误", JOptionPane.ERROR_MESSAGE);
                    return; // 如果格式错误，停止执行
                }
                char[] passwordChars = passwordField.getPassword();
                String password = new String(passwordChars);

                // 这里可以添加验证逻辑
                String WHERE = "employeeID = '"+username+"'";
                boolean isPass = authenticate(ID, password);
                if (isPass) {
                	new EmployeeOperationsUI();
                	frame.dispose();
                } else {
                    JOptionPane.showMessageDialog(frame, "用户名或密码错误！", "错误", JOptionPane.ERROR_MESSAGE);
                }
            }
        });

        JButton cancelButton = new JButton("取消");
        cancelButton.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                usernameField.setText("");
                passwordField.setText("");
                new SupermarketLoginUI();
                frame.dispose();
            }
        });

        buttonPanel.add(loginButton);
        buttonPanel.add(cancelButton);
        frame.add(buttonPanel);

        // 显示窗口
        frame.setLocationRelativeTo(null);
        frame.setResizable(false);
        frame.setVisible(true);
    }
	private boolean authenticate(int userID, String password) {
        Connection connection = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            // 获取数据库连接
            connection = LinkDateBase.getConnection();

            // SQL 查询
            String sql = "SELECT staffPassword FROM staff WHERE staffID = ?";
            pstmt = connection.prepareStatement(sql);
            pstmt.setInt(1, userID);

            // 执行查询
            rs = pstmt.executeQuery();

            // 检查结果
            if (rs.next()) {
                String storedPassword = rs.getString("staffPassword");
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
