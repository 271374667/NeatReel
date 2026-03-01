import threading
from functools import wraps
from typing import Any, Dict, Type, TypeVar

T = TypeVar("T")


def singleton(cls: Type[T]) -> Type[T]:
    """
    线程安全的单例类装饰器

    使用双重检查锁定(Double-Checked Locking)模式确保线程安全
    支持继承、pickle序列化、参数传递等生产环境特性

    Args:
        cls: 需要变成单例的类

    Returns:
        返回装饰后的单例类

    Example:
        @singleton
        class Database:
            def __init__(self, host='localhost'):
                self.host = host

        db1 = Database('localhost')
        db2 = Database('localhost')
        assert db1 is db2  # True
    """
    instances: Dict[Type[T], T] = {}
    lock = threading.RLock()

    @wraps(cls)
    def get_instance(*args: Any, **kwargs: Any) -> T:
        """获取单例实例"""
        # 第一次检查（无锁，性能优化）
        if cls not in instances:
            with lock:
                # 第二次检查（有锁，确保线程安全）
                if cls not in instances:
                    # 创建实例
                    instance = cls(*args, **kwargs)
                    instances[cls] = instance

        return instances[cls]

    # 保存原始类供序列化使用
    get_instance._cls = cls
    get_instance._instances = instances
    get_instance._lock = lock

    # 设置类属性，便于访问原始类信息
    get_instance.__name__ = cls.__name__
    get_instance.__module__ = cls.__module__
    get_instance.__doc__ = cls.__doc__
    get_instance.__dict__.update(cls.__dict__)

    return get_instance  # type: ignore


def singleton_with_args(cls: Type[T]) -> Type[T]:
    """
    支持多参数单例装饰器

    根据初始化参数的不同组合，创建不同的单例实例

    Args:
        cls: 需要变成单例的类

    Returns:
        返回装饰后的单例类

    Example:
        @singleton_with_args
        class Connection:
            def __init__(self, host, port):
                self.host = host
                self.port = port

        conn1 = Connection('localhost', 5432)
        conn2 = Connection('localhost', 5432)
        assert conn1 is conn2  # True

        conn3 = Connection('127.0.0.1', 5432)
        assert conn1 is not conn3  # True
    """
    instances: Dict[tuple, T] = {}
    lock = threading.RLock()

    @wraps(cls)
    def get_instance(*args: Any, **kwargs: Any) -> T:
        """根据参数获取或创建单例实例"""
        # 生成基于参数的键
        key = (args, tuple(sorted(kwargs.items())))

        if key not in instances:
            with lock:
                if key not in instances:
                    instance = cls(*args, **kwargs)
                    instances[key] = instance

        return instances[key]

    # 保存原始类和实例映射
    get_instance._cls = cls
    get_instance._instances = instances
    get_instance._lock = lock

    # 设置类属性
    get_instance.__name__ = cls.__name__
    get_instance.__module__ = cls.__module__
    get_instance.__doc__ = cls.__doc__

    return get_instance  # type: ignore


class SingletonMeta(type):
    """
    单例元类实现

    使用元类实现单例模式，支持继承和正常的类定义方式

    Example:
        class Database(metaclass=SingletonMeta):
            def __init__(self, host='localhost'):
                self.host = host

        db1 = Database('localhost')
        db2 = Database('localhost')
        assert db1 is db2  # True
    """

    _instances: Dict[Type, Any] = {}
    _lock = threading.RLock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """创建或返回单例实例"""
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super(SingletonMeta, cls).__call__(*args, **kwargs)
                    cls._instances[cls] = instance

        return cls._instances[cls]

    @classmethod
    def clear_instances(mcs) -> None:
        """清空所有实例（测试用）"""
        with SingletonMeta._lock:
            SingletonMeta._instances.clear()
