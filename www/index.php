<!DOCTYPE html>
<html>
<head>
    <title>Welcome to WinPHP</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding-top: 100px; }
        h1 { color: #3b82f6; }
        .info { background: #1e293b; display: inline-block; padding: 20px; border-radius: 8px; border: 1px solid #334155; }
    </style>
</head>
<body>
    <h1>WinPHP Server is Running Successfully!</h1>
    <div class="info">
        <p>PHP Version: <?php echo phpversion(); ?></p>
        <p>Document Root: <code><?php echo $_SERVER['DOCUMENT_ROOT']; ?></code></p>
        <p><a href="/phpmyadmin" style="color: #10b981;">Open phpMyAdmin</a></p>
    </div>
</body>
</html>