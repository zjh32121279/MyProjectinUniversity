package homework;

import javax.swing.*;
import java.awt.*;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;

public class SupermarketLoginUI {
    public SupermarketLoginUI() {
        // 创建主窗口
        JFrame frame = new JFrame("超市管理系统登录");
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setSize(300, 200);
        frame.setLayout(new GridLayout(4, 1));

        // 添加欢迎信息
        JLabel welcomeLabel = new JLabel("欢迎来到超市管理系统", SwingConstants.CENTER);
        frame.add(welcomeLabel);

        // 创建用户登录按钮
        JButton userLoginButton = new JButton("用户登录");
        userLoginButton.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                new UserLoginUI();
                frame.dispose();
            }
        });
        frame.add(userLoginButton);

        // 创建员工登录按钮
        JButton employeeLoginButton = new JButton("员工登录");
        employeeLoginButton.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                new EmployeeLoginUI();
                frame.dispose();
            }
        });
        frame.add(employeeLoginButton);

        // 创建经营者登录按钮
        JButton managerLoginButton = new JButton("经营者登录");
        managerLoginButton.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                new ManagerLoginUI();
                frame.dispose();
            }
        });
        frame.add(managerLoginButton);
        frame.setResizable(false);
        frame.setLocationRelativeTo(null);

        // 显示窗口
        frame.setVisible(true);
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> new SupermarketLoginUI());
    }
}