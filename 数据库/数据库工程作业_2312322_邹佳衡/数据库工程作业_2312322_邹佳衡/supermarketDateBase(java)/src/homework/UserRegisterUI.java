package homework;

import javax.swing.*;
import java.awt.*;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

public class UserRegisterUI {
	public UserRegisterUI() {
		JFrame frame = new JFrame("用户注册");
        frame.setSize(500, 300);
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setLocationRelativeTo(null);
        frame.setLayout(new BorderLayout());

        // 创建面板并设置布局
        JPanel panel = new JPanel();
        panel.setLayout(new GridLayout(6, 2, 10, 10));
        JLabel welcome = new JLabel("欢迎新用户注册。");
        JLabel tips = new JLabel("密码最多11位，只能由大小写字符和数字组成，编号由系统生成。");

        // 添加组件到面板
        JLabel nameLabel = new JLabel("姓名:");
        JTextField nameField = new JTextField(10);

        JLabel phoneLabel = new JLabel("电话（可以不填）:");
        JTextField phoneField = new JTextField(10);

        JLabel userIdLabel = new JLabel("用户编号（系统自动生成，即用户名）:");
        JTextField userIdField = new JTextField(10);
        userIdField.setEditable(false); // 设置为不可编辑

        JLabel passwordLabel1 = new JLabel("密码:");
        JPasswordField passwordField1 = new JPasswordField(10);

        JLabel passwordLabel2 = new JLabel("确认密码:");
        JPasswordField passwordField2 = new JPasswordField(10);

        JButton submitButton = new JButton("确定");
        JButton cancelButton = new JButton("取消");

        // 添加动作监听器
        submitButton.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                String name = nameField.getText().trim();
                String phone = phoneField.getText().trim();
                String password1 = new String(passwordField1.getPassword());
                String password2 = new String(passwordField2.getPassword());
                
                if(name.isEmpty()||password1.isEmpty()||password2.isEmpty()) {
                	JOptionPane.showMessageDialog(frame, "信息不全");
                	return;
                }

                // 验证名字格式
                if (!name.matches("[a-zA-Z\\u4E00-\\u9FA5]{1,45}")) {
                    JOptionPane.showMessageDialog(frame, "姓名必须由大小写字母或汉字组成，且长度不超过45位！", "错误", JOptionPane.ERROR_MESSAGE);
                    return;
                }

                // 验证电话格式（如果电话不为空）
                if (!phone.isEmpty() && !phone.matches("[\\d#*]{1,11}")) {
                    JOptionPane.showMessageDialog(frame, "电话必须由数字、#和*组成，且长度不超过11位！", "错误", JOptionPane.ERROR_MESSAGE);
                    return;
                }

                // 验证密码格式
                if (!password1.matches("[a-zA-Z0-9]{1,11}")) {
                    JOptionPane.showMessageDialog(frame, "密码必须由大小写字母和数字组成，且长度不超过11位！", "错误", JOptionPane.ERROR_MESSAGE);
                    return;
                }

                if (!password1.equals(password2)) {
                    JOptionPane.showMessageDialog(frame, "两次输入的密码不一致！", "错误", JOptionPane.ERROR_MESSAGE);
                    return;
                }
                String sql1,sql2;
                if(!phone.isEmpty()) {
                	sql1 = "insert into custom (customName, customPhone, customPassword) value ('" + name + "','" + phone + "','" + password1 + "');";
                	sql2 = "select customID from custom where customName = '"+name+"' and customPhone = '"+phone+"' and customPassword = '"+password1+"';";
                }
                else {
                	sql1 = "insert into custom (customName, customPhone, customPassword) value ('" + name + "'," + "null" + ",'" + password1 + "');";
                	sql2 = "select customID from custom where customName = '"+name+"' and customPhone = "+"null"+" and customPassword = '"+password1+"';";
                }
                boolean isInsert = register(sql1);
                if(isInsert) {
                	String ID = getCustomID(sql2);
                	userIdField.setText(ID);
                	JOptionPane.showMessageDialog(frame, "注册成功！请记住您的用户编号（用户名）");
                }else {
                	return;
                }
            }
        });

        cancelButton.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
            	new UserLoginUI();
                frame.dispose();
            }
        });

        // 将组件添加到面板
        panel.add(nameLabel);
        panel.add(nameField);
        panel.add(phoneLabel);
        panel.add(phoneField);
        panel.add(userIdLabel);
        panel.add(userIdField);
        panel.add(passwordLabel1);
        panel.add(passwordField1);
        panel.add(passwordLabel2);
        panel.add(passwordField2);
        panel.add(submitButton);
        panel.add(cancelButton);
        
        frame.setResizable(false);
        frame.add(welcome, BorderLayout.NORTH);
        frame.add(tips, BorderLayout.SOUTH);
        frame.add(panel,BorderLayout.CENTER);
        frame.setVisible(true);
	}
	
	private boolean register(String sql) {
		Connection connection = null;
        PreparedStatement stmt = null;
        int rs ;
        
		try {
			connection = LinkDateBase.getConnection();
		} catch (SQLException e) {
			// TODO Auto-generated catch block
			System.out.println("注册失败！");
			e.printStackTrace();
			return false;
		}
		try {
			stmt = connection.prepareStatement(sql);
		} catch (SQLException e) {
			// TODO Auto-generated catch block
			System.out.println("注册失败！");
			e.printStackTrace();
			return false;
		}
		try {
			rs = stmt.executeUpdate();
		} catch (SQLException e) {
			// TODO Auto-generated catch block
			System.out.println("注册失败！");
			e.printStackTrace();
			return false;
		}
		return true;
	}
	private String getCustomID(String sql) {
		Connection connection = null;
        Statement stmt = null;
        ResultSet rs = null;
        try {
			connection = LinkDateBase.getConnection();
		} catch (SQLException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		try {
			stmt = connection.createStatement();
		} catch (SQLException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		try {
			rs = stmt.executeQuery(sql);
		} catch (SQLException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		Integer result = 0;
		try {
			Integer temp;
			while(rs.next()) {
				temp = rs.getInt("customID");
				result = result > temp ? result : temp;
			}
		} catch (SQLException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		return result.toString();
	}
}
