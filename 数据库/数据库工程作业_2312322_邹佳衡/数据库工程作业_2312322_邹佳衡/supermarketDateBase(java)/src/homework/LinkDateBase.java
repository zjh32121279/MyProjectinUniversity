package homework;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import javax.swing.SwingUtilities;

public class LinkDateBase {
    public static final String url = "jdbc:mysql://localhost:3306/supermarketdatabase";
    public static final String username = "root";
    public static final String password = "zjh32121279";

    private static Connection connection = null;
    private static Statement statement = null;
    private static ResultSet resultSet = null;

    public static Connection getConnection() throws SQLException {
        if (connection == null || connection.isClosed()) {
            try {
                Class.forName("com.mysql.cj.jdbc.Driver");
                System.out.println("加载驱动器成功");
            } catch (ClassNotFoundException e) {
                System.out.println("加载驱动器失败!");
                e.printStackTrace();
            }
            connection = DriverManager.getConnection(url, username, password);
            System.out.println("连接数据库成功");
        }
        return connection;
    }

    public static void closeResources(Connection conn, Statement stmt, ResultSet rs) {
        try {
            if (rs != null) rs.close();
            if (stmt != null) stmt.close();
            if (conn != null) conn.close();
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        try {
            Connection conn = getConnection();
            statement = conn.createStatement();
            System.out.println("创建Statement成功");
        } catch (SQLException e) {
            System.out.println("创建Statement失败！");
            e.printStackTrace();
        }
        SwingUtilities.invokeLater(() -> new SupermarketLoginUI());
    }
}